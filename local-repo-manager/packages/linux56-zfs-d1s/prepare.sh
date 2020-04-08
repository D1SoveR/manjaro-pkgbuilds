#!/bin/bash

# Clone Manjaro's PKGBUILD for ZFS module for Linux 5.6
git clone --depth 1 https://gitlab.manjaro.org/packages/extra/linux56-extramodules/spl_zfs.git .

# Apply required changes to PKGBUILD to customise package name and
# modify its dependencies to use custom kernel package
patch -Np1 -i "$prepare_dir/pkgbuild-changes.patch"
