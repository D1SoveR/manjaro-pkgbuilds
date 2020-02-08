import configparser
import os
import os.path
import sys

def on_root_mount(path):

	while path != "/":
		if os.path.ismount(path):
			return False
		path = os.path.dirname(path)
	return True

def parse_config(config_file):

	"""
	Helper method to perform all the validation on the provided configuration file.
	It throws if the configuration file is not readable, or if there are issues with
	any of the paths provided in the config.
	Returns the flat config dictionary with all the valid options.
	"""

	if not os.path.isfile(config_file) or not os.access(config_file, os.R_OK):
		raise RuntimeError("Configuration file at {0} could not be read".format(config_file))

	config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
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
