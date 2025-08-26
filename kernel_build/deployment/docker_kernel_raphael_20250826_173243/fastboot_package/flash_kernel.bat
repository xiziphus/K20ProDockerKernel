@echo off
REM Kernel flashing script for K20 Pro (raphael)
REM WARNING: This will replace your kernel - backup first!

echo Flashing Docker-enabled kernel for K20 Pro...

REM Flash kernel and DTB separately
fastboot flash kernel kernel.img
fastboot flash dtb dtb.img

echo Kernel flashed successfully!
echo Rebooting device...
fastboot reboot
pause
