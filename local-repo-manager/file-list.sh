#!/bin/bash
# Little helper to generate the list of files in sources and their hashes.
# This here in order for me not to have to update that part of PKGBUILD manually.

mapfile -t sources < <(find . -depth -type f -not \( -regex './[A-Z]+' -or \( -executable -and -not -iname 'setup.py' \) \) | sed 's/^\.\///')
mapfile -t checksums < <(sha256sum "${sources[@]}" | awk '{print $1}')

last_index=$((${#sources[@]}-1))

for i in "${!sources[@]}"; do
  if [ $i == 0 ]; then echo -n "source=("; else echo -n "        "; fi
  echo -n "'${sources[$i]}'"
  if [ $i == $last_index ]; then echo ")"; else echo ""; fi
done

for i in "${!checksums[@]}"; do
  if [ $i == 0 ]; then echo -n "sha256sums=("; else echo -n "            "; fi
  echo -n "'${checksums[$i]}'"
  if [ $i == $last_index ]; then echo ")"; else echo ""; fi
done
