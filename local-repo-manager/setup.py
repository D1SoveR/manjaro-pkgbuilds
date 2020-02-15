#!/usr/bin/env python3

from sys import exit
from setuptools import setup, find_packages

def envfile_to_params(data):
	params = filter(lambda x: len(x) == 2, map(lambda x: x.strip().split("="), data.splitlines()))
	return { k: v[1:-1] if v.startswith('"') and v.endswith('"') else v for (k, v) in params }

# Using the version from PKGBUILD for less duplication
with open("./PKGBUILD", mode="rt", encoding="utf-8") as fp:
	pkgbuild_params = envfile_to_params(fp.read())
	pkgbuild_params["pkgname_"] = pkgbuild_params["pkgname"].replace("-", "_")

setup(
	name=pkgbuild_params["pkgname_"],
	version=pkgbuild_params["pkgver"],
	author='Mikołaj "D1SoveR" Banasik',
	author_email="d1sover@gmail.com",
	description=pkgbuild_params["pkgdesc"],
	url=pkgbuild_params["url"],
	classifiers=["License :: OSI Approved :: GNU General Public License v3 (GPLv3)"],

	packages=find_packages(),
	entry_points={"console_scripts": [
		"{0[pkgname]} = {0[pkgname_]}:main".format(pkgbuild_params)
	]}
)
