#!/usr/bin/env python3

import os.path
from shutil import copy
from subprocess import run, STDOUT
import sys
import traceback

from .build import get_packages, get_build_artifacts, run_within_container, build_package
from .config import parse_arguments, parse_config, on_root_mount
from .log import LogToFile, LogToStdout
from .repo import get_repo
from .util import TempDirectory, custom_exception_handler

def main():

	# OVERRIDING EXCEPTION HANDLER
	# ============================
	# This is to improve the CLI interface, by skipping things like
	# long stacktraces when we throw known errors (like validating configs).
	# Only certain types of errors receive that treament, unexpected errors
	# are still logged the default way.
	sys.excepthook = custom_exception_handler

	# ARGUMENT PARSING AND VALIDATION
	# ===============================
	# These two lines obtain the arguments from the command line (validation done by ArgumentParser),
	# then the configuration file is parsed (validation of its options done by the method).
	args = parse_arguments(sys.argv[1:])
	config = parse_config(args.config_file)

	# This bit is needed due to the fact that nspawn container's overlay FS does not span multiple
	# mounts, so if any of these things are not on root partition, they won't be accessible in
	# the container.
	if args.action != "build":
		if not on_root_mount(os.path.abspath(sys.argv[0])):
			raise RuntimeError("Manager executable needs to be on the root partition")
		if not on_root_mount(config["packages_dir"]):
			raise RuntimeError("Packages directory needs to be on the root partition")
		if not on_root_mount(config["repository_file"]):
			raise RuntimeError("Repository file needs to be on the root partition")

	# HANDLING ACTIONS
	# ================

	# CONFIGURATION PRINT-OUT
	# Debug options to print out the current state of the configuration file.
	# Useful to help in identifying any misconfiguration.
	if args.action == "config":

		max_key_length = max(map(len, config.keys()))
		print("Repository manager configuration:\n")
		for key, value in config.items():
			print("  {0}: ".format(key).ljust(max_key_length + 4), value)
		print("")

	# LISTING PACKAGES HANDLED BY THE MANAGER
	# Iterates over all the entries in the packages direcotry, and lists them,
	# along with git repositories they originate from. For ones that don't have
	# valid preparation script or don't have the repo, it'll provide warning line.
	elif args.action == "list":

		packages = get_packages(config["packages_dir"])
		if not len(packages):
			print("No packages currently handled by the manager")
		else:
			max_key_length = max(map(len, packages.keys()))
			print("Following packages are handled by the manager:\n")
			for name, repo in packages.items():
				print("  {0}: ".format(name).ljust(max_key_length + 4), repo if repo else "[NO REPOSITORY IDENTIFIED]")
			print("")

	# LISTING PACKAGES IN LOCAL REPO
	# Fairly straightforward process, the local database repository is queried
	# for packages, and the information pretty-printed to the terminal.
	elif args.action == "list-existing":

		repo = get_repo(config["repository_file"])
		if not len(repo):
			print("No packages in the local repository")
		else:
			max_key_length = max(map(len, repo.keys()))
			print("Following packages are in local repository:\n")
			for name, versions in repo.items():
				print("  {0}: ".format(name).ljust(max_key_length + 4), versions[0])
			print("")

	# SCHEDULING UPDATE OF ALL THE PACKAGES
	# Main and most complex part of the manager, this code sets up the nspawn container
	# along with temporary directory to bind as target for build artifacts, then runs
	# itself in that container with `build` action, doing the actual build.
	# Once the build process is complete, we check for the status.
	# If there was a failure, none of the packages are added and the user is prompted
	# to check the logs and resolve the issue.
	# If it was successful, then the new packages (if there are any, we don't rebuild
	# if the package is not newer than what's in local repository) are copied to repository
	# directory and added to the repo DB.
	elif args.action == "update":

		print("Setting up container to build new packages in...")
		with TempDirectory() as pkgdest:

			# We run python3 via env as nspawn expects actual binary,
			# and the manager is a Python script; we pass through config
			# location and provide package destination directory.
			container_args = [
				"/usr/bin/env", "python3", os.path.abspath(sys.argv[0]),
				"--config", args.config_file, "build", "--pkgdest", pkgdest
			]

			# Should any issues occur during the build process, we make sure to print
			# all the exception details into whatever the log target is (terminal or file),
			# and raise known RuntimeError - this is to prevent spamming systemd journals
			# when update is executed from the timer.
			try:

				with (LogToFile(config["log_dir"]) if args.logging else LogToStdout()) as (fp, log_dest):
					print(f"(build process will be logged to {log_dest})\n")
					try:
						run_within_container(container_args, pkgdest, extra_params=config["nspawn_params"], log_output=fp)
					except Exception as e:
						traceback.print_exception(*sys.exc_info(), file=fp)
						raise e

			except Exception as e:
				exc = RuntimeError("Build process has failed due to unexpected errors\nCheck the build log to investigate the cause of the issue")
				exc.with_traceback(sys.exc_info()[2])
				raise exc

			print("\nBuild complete, temporary container terminated")

			# It is possible that we have no new build artifacts even if the build process
			# was successful, as we only build if the package is newer than what's in local repo.
			build_artifacts = get_build_artifacts(pkgdest)
			if not len(build_artifacts):
				print("No new packages have been built")
			else:
				print("Copying artifacts to local repository directory...")
				copied_artifacts = [copy(x, config["repository_dir"]) for x in build_artifacts]
				print("Adding artifacts to local repository...\n")
				run(
					["/usr/bin/repo-add", "--new", config["repository_file"]] + copied_artifacts,
					check=True, stdout=sys.stdout, stderr=sys.stderr
				)

				print("\nNew packages added to the repository")
				print("Run pacman -Syyu to install them")

	# BUILD PACKAGES
	# This action conducts the actual build process for all the packages.
	# It's intended to be run within the nspawn container, through `update` action,
	# and shouldn't be run directly on the host system.
	elif args.action == "build":

		# We override the sudoers file within the container to allow the non-root user to
		# use sudo for root operations without having to provide password (primarily for
		# installing dependencies for makepkg)
		print("Configuring sudo permissions...")
		with open("/etc/sudoers", mode="wt", encoding="utf8") as fp:
			print("ALL ALL=(ALL) NOPASSWD: ALL", file=fp)

		# We're running the nspawn container without systemd init,
		# so whatever the network interface is, it will need to be initialised and configured
		# manually, via dhclient command.
		print("Configuring internal network connection...")
		run(["/usr/bin/dhclient", "host0"], check=True, stdout=sys.stdout, stderr=STDOUT)

		print("Retrieving package info from local repository...")
		repo = get_repo(config["repository_file"])

		# We skip over the packages that don't have valid source
		packages_to_build = tuple(key for (key, item) in get_packages(config["packages_dir"]).items() if item)
		print("Will build following packages:")
		for item in packages_to_build:
			print(f"* {item}")

		for item in packages_to_build:
			print(f"\nBUILD FOR {item}\n===========================")
			build_package(repo, os.path.join(config["packages_dir"], item), args.pkgdest)
