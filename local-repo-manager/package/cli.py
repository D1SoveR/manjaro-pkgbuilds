#!/usr/bin/env python3
if __name__ != "__main__":
	raise ImportError("This file is not meant to be imported, only used as CLI interface")

import argparse
import os.path
import sys

from config import parse_config
from build import get_packages

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
	"action",
	metavar="ACTION",
	choices=["config", "list", "list-existing", "update", "build"],
	help="What should the manager do"
)
parser.add_argument(
	"-c", "--config",
	required=False,
	metavar="CONFIG-FILE-LOCATION",
	default="/etc/local-repo.conf",
	type=os.path.abspath,
	help="Alternative location for the manager configuration file",
	dest="config_file"
)

# ARGUMENT PARSING AND VALIDATION
# ===============================
# These two lines obtain the arguments from the command line (validation done by ArgumentParser),
# then the configuration file is parsed (validation of its options done by the method).
args = parser.parse_args()
config = parse_config(args.config_file)

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