#!/bin/bash

# Clone Manjaro's PKGBUILD for Linux 5.5 kernel
git clone --depth 1 https://gitlab.manjaro.org/packages/core/linux55.git .

# Copy over the following patches to apply to kernel:
# * Patch to un-GPL some kernel symbols to make ZFS module buildable again
# * Valve's fsync patch, for improved performance in Windows games
cp $prepare_dir/{zfs-fix,fsync}.patch .

# Apply required changes to PKGBUILD to customise package name and
# ensure the patches above are applied
patch -Np1 -i "$prepare_dir/pkgbuild-changes.patch"
