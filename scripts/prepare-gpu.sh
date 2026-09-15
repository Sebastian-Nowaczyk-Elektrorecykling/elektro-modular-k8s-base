#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname "$0")/lib/common.sh"
root_required
debian_required
export DEBIAN_FRONTEND=noninteractive
# Debian archive signatures cover these components; preserve third-party source files.
cat >/etc/apt/sources.list.d/elektro-gpu.sources <<'EOF'
Types: deb
URIs: https://deb.debian.org/debian
Suites: trixie trixie-updates
Components: main contrib non-free non-free-firmware
Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg

Types: deb
URIs: https://security.debian.org/debian-security
Suites: trixie-security
Components: main contrib non-free non-free-firmware
Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg
EOF
apt-get update
arch=$(dpkg --print-architecture)
apt-get install -y "linux-headers-$arch" build-essential dkms mokutil pciutils \
    firmware-linux-free firmware-misc-nonfree firmware-amd-graphics firmware-intel-graphics \
    mesa-vulkan-drivers mesa-opencl-icd libgl1-mesa-dri ocl-icd-libopencl1 clinfo vulkan-tools
report=/var/log/elektro-gpu-packages.log
: >"$report"
# Install every available userspace stack in our vendor matrix, even before a GPU is added.
# Package availability differs by CPU architecture; record each absence explicitly.
for package in intel-opencl-icd libze-intel-gpu1 intel-media-va-driver-non-free \
    rocm-opencl-icd rocminfo libhsa-runtime64-1 libamdhip64-5 firmware-nvidia-graphics; do
    if apt-cache policy "$package" | awk '/Candidate:/ {found=($2 != "(none)")} END {exit !found}'; then
        apt-get install -y "$package"
        printf 'installed %s\n' "$package" >>"$report"
    else
        printf 'unavailable on %s: %s\n' "$arch" "$package" | tee -a "$report" >&2
    fi
done
# NVIDIA kernel drivers can conflict with nouveau and depend on GPU generation.
# Install them only on NVIDIA hardware; nouveau/Mesa remains available for other nodes.
if lspci -Dn | awk '$2 ~ /^03/ && $3 ~ /^10de:/ {found=1} END {exit !found}'; then
    apt-get install -y nvidia-detect
    driver=${NVIDIA_DRIVER_PACKAGE:-nvidia-driver}
    [[ $driver =~ ^nvidia-(open-kernel-dkms|driver|tesla-[0-9]+-driver)$ ]] || die 'Unrecognized NVIDIA_DRIVER_PACKAGE.'
    nvidia-detect | tee -a "$report"
    apt-get install -y "$driver" nvidia-smi nvidia-opencl-icd
    if mokutil --sb-state 2>/dev/null | grep -qi 'SecureBoot enabled'; then
        log 'Secure Boot is enabled. Enroll the Debian DKMS MOK at the next reboot; see docs/gpu.md.'
    fi
fi
# Toolkit is required for k3s to discover the NVIDIA runtime. It is installed on all workers.
install -d -m 0755 /usr/share/keyrings
tmpdir=$(mktemp -d)
trap 'rm -rf "$tmpdir"' EXIT
download https://nvidia.github.io/libnvidia-container/gpgkey "$tmpdir/nvidia.asc"
gpg --batch --yes --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg "$tmpdir/nvidia.asc"
printf 'deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://nvidia.github.io/libnvidia-container/stable/deb/%s /\n' "$arch" \
    >/etc/apt/sources.list.d/nvidia-container-toolkit.list
apt-get update
apt-get install -y nvidia-container-toolkit
# Do not run nvidia-ctk runtime configure against the system containerd: k3s owns a separate one.
install -d /etc/cdi
if command -v nvidia-smi >/dev/null && nvidia-smi >/dev/null 2>&1; then
    nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml
fi
log "GPU prerequisites prepared. Review $report, reboot, then run scripts/verify-gpu.sh."
