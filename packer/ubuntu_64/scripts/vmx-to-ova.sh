#!/usr/bin/env bash

set -e
if [ ! -z "${DEBUG}" ]; then
  set -x
fi

DEPENDENCIES=("ovftool")
for dep in "${DEPENDENCIES[@]}"
do
  if [ ! $(which ${dep}) ]; then
      echo "${dep} must be available."
      exit 1
  fi
done

print_usage () {
  echo "vmx-to-ova.sh - Converts a VMX to an OVA and deletes the VMX if successful."
  echo "-s=<source_vmx_folder>    The directory that contains the VMX."
}

while getopts "s:" opt; do
  case $opt in
    s) SOURCE_DIR=$OPTARG ;;
    \?)
      echo "Invalid option: -$OPTARG" >&2
      print_usage
      exit 1
      ;;
  esac
done

if [[ -z "${SOURCE_DIR}" ]]; then
  echo "Source VMX folder must be specified"
  print_usage
  exit 1
fi

for vmx in "$SOURCE_DIR"/*.vmx; do
  name=$(basename "${vmx}" .vmx)
  ovftool -dm=thin --compress=1 "${vmx}" "${SOURCE_DIR}/${name}.ova"
done

cd "${SOURCE_DIR}" && rm *.vmdk *.vmx *.vmxf *.vmsd *.nvram