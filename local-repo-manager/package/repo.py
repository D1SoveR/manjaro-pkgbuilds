#!/usr/bin/env python3

import tarfile
from collections import defaultdict
from subprocess import run
from functools import cmp_to_key

def pacman_ver_compare(versionOne, versionTwo):
	return int(run(["/usr/bin/vercmp", versionOne, versionTwo], capture_output=True).stdout)

@cmp_to_key
def pacman_newest_first(a, b):
	return pacman_ver_compare(b, a)

def is_newer(version, reference_version):
	return pacman_ver_compare(version, reference_version) > 0

def get_repo(repository_file):

	"""
	Function that returns a map of all the packages currently held in the local repository,
	along with the versions, going from most recent to oldest.
	Used to compare the version of the package being built, and determining whether
	it needs to be rebuilt.
	"""

	versions = defaultdict(list)

	with tarfile.open(repository_file, mode="r:xz") as tf:
		for item in tf:
			if item.isfile() and item.name.endswith("desc"):
				with tf.extractfile(item) as fp:
					desc_file = fp.read().decode("utf8")
				name = None
				version = None
				for line in desc_file.splitlines():
					if line == r"%NAME%":
						name = False
					elif line == r"%VERSION%":
						version = False
					elif name == False:
						name = line
					elif version == False:
						version = line
					if name and version:
						break
				versions[name].append(version)
				if len(versions[name]) > 1:
					versions[name].sort(pacman_newest_first)

	return dict((name, tuple(versions)) for name, versions in sorted(versions.items()))