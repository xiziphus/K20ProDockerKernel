#!/bin/bash
# Kernel build environment setup

export KERNEL_SOURCE='/Users/prateeksingh/Documents/PS/geminicli/dockerkernel/Android-Container/kernel_source'
export KERNEL_OUTPUT='/Users/prateeksingh/Documents/PS/geminicli/dockerkernel/Android-Container/kernel_output'
export ARCH='arm64'
export SUBARCH='arm64'

# Add to PATH if needed
# export PATH=$ANDROID_NDK_ROOT/toolchains/llvm/prebuilt/linux-x86_64/bin:$PATH

echo 'Kernel build environment configured'
echo 'Kernel source: $KERNEL_SOURCE'
echo 'Build output: $KERNEL_OUTPUT'
