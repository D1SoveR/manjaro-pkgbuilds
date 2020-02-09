from argparse import ArgumentParser
from configparser import ConfigParser, ExtendedInterpolation
import os
import os.path

def on_root_mount(path):

	"""
	Helper method helping to determine whether given path is on the same
	partition as root directory. We need to check for it due to limiations
	of overlay FS not spanning multiple mounts.
	Essentially, if the required file were on different mount, it wouldn't
	then show up in the nspawn container.
	"""

	while path != "/":
		if os.path.ismount(path):
			return False
		path = os.path.dirname(path)
	return True

def parse_arguments(args):

	"""
	This method parses command line arguments to figure out which part of the program
	should be executed.
	The main argument is the action command, which determines what the manager should do;
	verify the config file, print the list of current packages, or try to update them.
	Some of these commands have extra arguments, like where to log the build process,
	or where to drop the build artifacts.
	It's intended for use from the main CLI function.
	"""

	parser = ArgumentParser(
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

	# Configure all of the main actions here
	subparsers = parser.add_subparsers(
		title="action",
		dest="action",
		required=True
	)

	# These actions are just listing information and have no extra configuration,
	# they're essentially there for basic debugging
	subparsers.add_parser("config", help="Shows all of the current configuration options")
	subparsers.add_parser("list", help="Lists all of the packages built by this manager")
	subparsers.add_parser("list-existing", help="Lists all the packages currently present in the local repo")

	# The update action schedules the build action within the nspawn container,
	# and adds any new packages to local repo afterwards
	action_update = subparsers.add_parser("update", help="Schedules update of all the packages")
	action_update.add_argument(
		"--no-log",
		action="store_false",
		dest="logging",
		required=False,
		help="If provided, outputs the logs of the build process to terminal instead of log file"
	)

	# The build action performs the actual building, and it's intended to be used within
	# the nspawn container by the `update` command. The --pkgdest argument should point
	# to the bind directory used to get the build artifacts out of the container
	action_build = subparsers.add_parser("build", help="Conducts the actual build process")
	action_build.add_argument(
		"--pkgdest",
		required=True,
		type=os.path.abspath,
		help="Location to which the built packages will be moved",
		dest="pkgdest"
	)

	return parser.parse_args(args)

def parse_config(config_file):

	"""
	Helper method to perform all the validation on the provided configuration file.
	It throws if the configuration file is not readable, or if there are issues with
	any of the paths provided in the config.
	Returns the flat config dictionary with all the valid options.
	"""

	if not os.path.isfile(config_file) or not os.access(config_file, os.R_OK):
		raise RuntimeError("Configuration file at {0} could not be read".format(config_file))

	config = ConfigParser(interpolation=ExtendedInterpolation())
	config.read([config_file])

	# Verify that the paths defined in the config exist
	temp = config["Paths"]["repository_dir"]
	if not os.path.isdir(temp) or not os.access(temp, os.W_OK | os.X_OK):
		raise RuntimeError("Repository directory at {0} could not be accessed".format(temp))

	# Verify that the repository DB either doesn't exist, or is readable and writable
	temp = config["Paths"]["repository_file"]
	if os.path.isfile(temp) and not os.access(temp, os.R_OK | os.W_OK):
		raise RuntimeError("Repository file at {0} could not be read and written to".format(temp))
	elif os.path.isdir(temp):
		raise RuntimeError("Repository file at {0} is a directory".format(temp))

	# Verify that the packages directory can be accessed and read from
	temp = config["Paths"]["packages_dir"]
	if not os.path.isdir(temp) or not os.access(temp, os.R_OK | os.X_OK):
		raise RuntimeError("Packages directory at {0} could not be accessed".format(temp))

	config_dict = { "config_file": config_file }
	for section in config.sections():
		config_dict.update(config[section])
	return config_dict
