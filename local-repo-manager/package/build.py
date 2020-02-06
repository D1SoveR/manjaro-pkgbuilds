import os
import os.path
import re

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
