#!/usr/bin/env bash

switch=$1
ssh admin@$switch <<'SSH'
enable
write erase now
reload now
'SSH'