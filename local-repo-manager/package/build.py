import os
import os.path
import pwd
import re
import subprocess
import sys

from util import TempDirectory

REPO_ADDRESS_GIT = re.compile(r'^(?:ssh|https?)://')

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

def run_within_container(command, *bind_dirs, extra_params=None, log_output=None):

	"""

	"""

	with TempDirectory("/") as container_base:

		args = [
            "systemd-nspawn",
            "--quiet",
            f"--directory={container_base}",
            "--volatile=overlay",
            "--as-pid2",
		]
		args.extend("--bind={0}".format(os.path.abspath(directory)) for directory in bind_dirs)

		if extra_params:
			args.extend(extra_params.split(" "))

		if type(command) == str:
			args.append(command)
		else:
			args.extend(command)

		subprocess.run(args, check=True, capture_output=False, stdout=log_output, stderr=subprocess.STDOUT)

def prepare_and_build(package_dir, destination_dir):

	temp_env = dict(os.environ)
	temp_env["prepare_dir"] = package_dir
	temp_env["PKGDEST"] = destination_dir
	username = pwd.getpwuid(1000).pw_name
	run_as_user = ["/usr/bin/sudo", "-E", "-u", username]

	with TempDirectory() as build_dir:

		os.chown(destination_dir, 1000, 1000)
		os.chown(build_dir, 1000, 1000)

		print("Preparing the package for build...")
		subprocess.run(run_as_user + ["/bin/bash", os.path.join(package_dir, "prepare.sh")], cwd=build_dir, env=temp_env, check=True, stdout=sys.stdout, stderr=subprocess.STDOUT)

		print("Building the package...")
		subprocess.run(run_as_user + ["/usr/bin/makepkg", "-sc"], cwd=build_dir, env=temp_env, check=True, stdout=sys.stdout, stderr=subprocess.STDOUT)

		print("Installing the new packages in the container...")
		install_args = ["/usr/bin/pacman", "--needed", "--noconfirm", "-U"]
		install_args.extend(filter(lambda x: x.endswith(".tar.xz"), os.listdir(destination_dir)))
		subprocess.run(install_args, cwd=destination_dir, check=True, stdout=sys.stdout, stderr=subprocess.STDOUT)