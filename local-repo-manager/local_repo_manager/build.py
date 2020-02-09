import os
import os.path
import pwd
import re
import subprocess
import sys

from repo import is_newer
from util import TempDirectory

MATCH_SRCINFO = re.compile(r'^\s*(epoch|pkgver|pkgrel|pkgname) = (.+)$')
REPO_ADDRESS_GIT = re.compile(r'^(?:ssh|https?)://')
LOCAL_USER_UID = 1000
RUN_AS_USER = ["/usr/bin/sudo", "-E", "-u", pwd.getpwuid(LOCAL_USER_UID).pw_name]

def get_packages(packages_dir):

	results = {}
	for dir_entry in os.scandir(packages_dir):
		if dir_entry.is_dir():
			try:
				repository = get_repository(dir_entry.path)
			except OSError:
				repository = None
			results[dir_entry.name] = repository
	return results

def get_repository(package_dir):

	with open(os.path.join(package_dir, "prepare.sh"), mode="rt", encoding="utf8") as fp:
		for line in fp:

			# Extracting repository from git command
			if line.startswith("git clone"):
				args = line.split(" ")[2:]
				for item in args:
					if REPO_ADDRESS_GIT.match(item):
						return item

	return None

def get_build_artifacts(directory):

	"""
	Helper method that returns the list of all .tar.xz files in given directory,
	as full absolute paths.
	It's used several places to provide arguments to commands that run on all the packages.
	"""

	artifacts = filter(lambda x: x.endswith(".tar.xz"), os.listdir(directory))
	full_paths = map(lambda x: os.path.join(directory, x), artifacts)
	return list(full_paths)

def get_packages_from_srcinfo(srcinfo):

	version = {}
	names = []

	for line in srcinfo.splitlines():
		match = MATCH_SRCINFO.match(line)
		if match:
			if match.group(1) == "pkgname":
				names.append(match.group(2))
			else:
				version[match.group(1)] = match.group(2)

	final_version = version["pkgver"]
	if "pkgrel" in version:
		final_version += "-" + version["pkgrel"]
	if "epoch" in version:
		final_version = version["epoch"] + ":" + final_version

	return dict((name, final_version) for name in names)

def run_within_container(command, *bind_dirs, extra_params=None, log_output=None):

	"""
	This function is used to run the given command inside of temporary nspawn container.
	Given the command, list of writable directories to bind between host and container,
	and any extra parameters (like network configuration, coming from the config),
	it executes the `systemd-nspawn` command with the host system as read-only root.

	It's used primarily to start the local repository manager with "build" action,
	which kicks off the actual build process.

	The output can be directed to something else than standard output using log_output argument.
	"""

	with TempDirectory("/") as container_base:

		args = ["systemd-nspawn", "--quiet", f"--directory={container_base}", "--volatile=overlay", "--as-pid2"]
		args.extend("--bind={0}".format(os.path.abspath(directory)) for directory in bind_dirs)
		if extra_params:
			args.extend(extra_params.split(" "))
		args.extend(command)

		subprocess.run(args, check=True, stdout=log_output, stderr=subprocess.STDOUT)

def build_package(repo, package_dir, destination_dir):

	"""
	This function performs the bulk of the work in the process of building a package.
	Given the location of scripts to set up package build and the destination to which the bundled artifact should be written,
	it creates temporary build directories, runs the prepare scripts, then checks the package version. If the one in the build dir
	is newer than what we already have in the local repository, building proceeds,.

	The package is also installed locally (in the container), in case any other packages have it as make dependency.
	"""

	temp_env = dict(os.environ)
	temp_env["prepare_dir"] = package_dir  # This env is used by prepare.sh scripts for reference to directory with all the patches
	temp_env["PKGDEST"] = destination_dir  # This env is used by makepkg to determine where to write the bundled build artifacts

	with TempDirectory() as build_dir:

		# We ensure both the build and artifact destination directories
		# can be written to by local user (since we can't run makepkg with root)
		os.chown(destination_dir, LOCAL_USER_UID, LOCAL_USER_UID)
		os.chown(build_dir, LOCAL_USER_UID, LOCAL_USER_UID)

		print("Preparing the package for build...")
		subprocess.run(
			RUN_AS_USER + ["/bin/bash", os.path.join(package_dir, "prepare.sh")],
			cwd=build_dir, env=temp_env, check=True, stdout=sys.stdout, stderr=subprocess.STDOUT
		)

		print("Checking package version (will not build if older or same as current)...")
		srcinfo = subprocess.run(
			RUN_AS_USER + ["/usr/bin/makepkg", "--printsrcinfo"],
			cwd=build_dir, check=True, capture_output=True
		).stdout.decode("utf8")

		package_versions = get_packages_from_srcinfo(srcinfo)
		if not any(is_newer(version, repo[name][0]) for name, version in package_versions.items()):
			print("None of the build artifacts are newer than contents of the local repository, skipping...")
			return

		print("Building the package...")
		subprocess.run(
			RUN_AS_USER + ["/usr/bin/makepkg", "-sc"],
			cwd=build_dir, env=temp_env, check=True, stdout=sys.stdout, stderr=subprocess.STDOUT
		)

		print("Installing the new packages in the container...")
		subprocess.run(
			["/usr/bin/pacman", "--needed", "--noconfirm", "-U"] + get_build_artifacts(destination_dir),
			cwd=destination_dir, check=True, stdout=sys.stdout, stderr=subprocess.STDOUT
		)
