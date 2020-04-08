#!/bin/bash
set -e

# Clone Manjaro's PKGBUILD for Linux 5.6 kernel
git clone --depth 1 https://gitlab.manjaro.org/packages/core/linux56.git .

# Check for the merge config script (needed to apply the configuration fragments),
# and throw an error if it can't be found
merge_script="$(pacman -Qql | grep 'merge_config\.sh' | sort -r | head -1)"
if [ -z "$merge_script" ]; then
  echo "Could not find any versions of merge_config.sh, cannot continue the build" 1>&2
  exit 1
fi

# Copy over the following patches to apply to kernel:
# * Patch to un-GPL some kernel symbols to make ZFS module buildable again
# * Valve's fsync patch, for improved performance in Windows games
# * Patch to ensure that in btrfs RAID 1 array with SSD and HDD, reads always go to SSD
#   (see https://patchwork.kernel.org/project/linux-btrfs/list/?submitter=182469)
cp $prepare_dir/{zfs-fix,fsync,btrfs-prefer-nonrotational}.patch .

# Copy over the configuration fragment re-enabling fully preemptive kernel
# (with the other patch in place we _can_ build ZFS module for one)
cp $prepare_dir/preempt.config .

# Apply required changes to PKGBUILD to customise package name and
# ensure the patches above are applied
patch -Np1 -i "$prepare_dir/pkgbuild-changes.patch"

# Apply the patch that incorporates the configuration changes from given fragments
# (replacing the placeholder "[merge_script]" with location of previously found
#  merge_config.sh script)
sed "s|\[merge_script\]|$merge_script|" "$prepare_dir/config.patch" | patch -Np1 -i -
