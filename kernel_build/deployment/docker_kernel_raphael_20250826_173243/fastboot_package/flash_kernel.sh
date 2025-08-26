#!/bin/bash
# Kernel flashing script for K20 Pro (raphael)
# WARNING: This will replace your kernel - backup first!

set -e

echo 'Flashing Docker-enabled kernel for K20 Pro...'

# Flash kernel and DTB separately
fastboot flash kernel kernel.img
fastboot flash dtb dtb.img

echo 'Kernel flashed successfully!'
echo 'Rebooting device...'
fastboot reboot
