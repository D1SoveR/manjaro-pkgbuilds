#!/usr/bin/env python3
if __name__ != "__main__":
	raise ImportError("This file is not meant to be imported, only used as CLI interface")

import argparse
import os.path
import sys

from config import parse_config, on_root_mount
from build import get_packages, run_within_container, prepare_and_build
from util import TempDirectory, get_all_mountpoints

import subprocess

# OVERRIDING EXCEPTION HANDLER
# ============================
# This is to improve the CLI interface, by skipping things like
# long stacktraces when we throw known errors (like validating configs).
# Only certain types of errors receive that treament, unexpected errors
# are still logged the default way.
original_excepthook = sys.excepthook
def custom_exception_handler(exctype, value, tb):
	if exctype == RuntimeError:
		print(value, file=sys.stderr)
	else:
		original_excepthook(exctype, value, tb)
sys.excepthook = custom_exception_handler

# ARGUMENT HANDLING
# =================
# The CLI interface is pretty straightforward - it takes single action
# command, with optional location of alternatice configuration file.
parser = argparse.ArgumentParser(
	description="Program used to manage the local packages repository, built with custom patches",
	formatter_class=argparse.ArgumentDefaultsHelpFormatter
)
parser.add_argument(
	"-c", "--config",
	required=False,
	default="/etc/local-repo.conf",
	type=os.path.abspath,
	help="Alternative location for the manager configuration file",
	dest="config_file"
)

subparsers = parser.add_subparsers(
	title="action",
	dest="action",
	required=True
)
subparsers.add_parser("config", help="Shows all of the current configuration options")
subparsers.add_parser("list", help="Lists all of the packages handled by this manager")

action_update = subparsers.add_parser("update", help="Schedules update of all the packages")
action_update.add_argument(
	"--no-log",
	action="store_false",
	dest="logging",
	required=False,
	help="If provided, outputs the logs of the build process to terminal instead of log file"
)

action_build = subparsers.add_parser("build", help="Conducts the actual build process")
action_build.add_argument(
	"--pkgdest",
	required=True,
	type=os.path.abspath,
	help="Location to which the built packages will be moved",
	dest="pkgdest"
)

# ARGUMENT PARSING AND VALIDATION
# ===============================
# These two lines obtain the arguments from the command line (validation done by ArgumentParser),
# then the configuration file is parsed (validation of its options done by the method).
args = parser.parse_args()
config = parse_config(args.config_file)

if args.action != "build":
	if not on_root_mount(os.path.abspath(sys.argv[0])):
		raise RuntimeError("Manager executable needs to be on the root partition")
	if not on_root_mount(config["packages_dir"]):
		raise RuntimeError("Packages directory needs to be on the root partition")

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

# SCHEDULING UPDATE OF ALL THE PACKAGES
elif args.action == "update":

	if args.logging:
		raise RuntimeError("Logging not yet implemented")
	print("Setting up container to build new packages in...")
	with TempDirectory() as pkgdest:

		args = [
			"/usr/bin/env", "python3", os.path.abspath(sys.argv[0]),
			"--config", args.config_file, "build", "--pkgdest", pkgdest
		]

		run_within_container(args, pkgdest, extra_params=config["nspawn_params"], log_output=sys.stdout)

		print("")
		print("Build complete, temporary container terminated")
		print("Adding packages to local repository...")

		args = ["/usr/bin/repo-add", "--new", config["repository_file"]]
		args.extend(map(lambda x: os.path.join(pkgdest, x), filter(lambda x: x.endswith(".tar.xz"), os.listdir(pkgdest))))
		print(f"ARGS: {args}")
		subprocess.run(args, check=True, stdout=sys.stdout, stderr=subprocess.STDOUT)

elif args.action == "build":

	print("Configuring internal network connection...")
	subprocess.run(["/usr/bin/dhclient", "host0"], check=True, stdout=sys.stdout, stderr=subprocess.STDOUT)

	packages_to_build = tuple(key for (key, item) in get_packages(config["packages_dir"]).items() if item)
	print("Will build following packages:")
	for item in packages_to_build:
		print(f"* {item}")
	print("")

	for item in packages_to_build:
		prepare_and_build(os.path.join(config["packages_dir"], item), args.pkgdest)
