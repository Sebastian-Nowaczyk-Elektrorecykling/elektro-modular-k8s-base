#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname "$0")/lib/common.sh"
root_required
debian_required
apt_prepare
export DEBIAN_FRONTEND=noninteractive
apt-get install -y open-iscsi nfs-common cryptsetup dmsetup lvm2 iptables nftables iproute2 \
    ethtool socat conntrack ebtables kmod pciutils chrony arping
swapoff -a
cp --preserve=all /etc/fstab /etc/fstab.elektro-backup
sed -ri '/^[[:space:]]*#/! { /[[:space:]]swap[[:space:]]/s/^/# elektro-disabled-swap /; }' /etc/fstab
# zram-generator otherwise recreates swap at the next boot.
mkdir -p /etc/systemd
if [[ -e /etc/systemd/zram-generator.conf ]]; then
    cp --preserve=all /etc/systemd/zram-generator.conf /etc/systemd/zram-generator.conf.elektro-backup
fi
printf '[zram0]\nzram-size = 0\n' >/etc/systemd/zram-generator.conf
cat >/etc/modules-load.d/elektro-k8s.conf <<'EOF'
overlay
br_netfilter
iscsi_tcp
dm_crypt
EOF
while IFS= read -r module; do modprobe "$module"; done </etc/modules-load.d/elektro-k8s.conf
cat >/etc/sysctl.d/90-elektro-k8s.conf <<'EOF'
net.ipv4.ip_forward = 1
net.bridge.bridge-nf-call-iptables = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.conf.all.rp_filter = 0
net.ipv4.conf.default.rp_filter = 0
fs.inotify.max_user_instances = 8192
fs.inotify.max_user_watches = 1048576
EOF
sysctl --system
systemctl enable --now iscsid chrony
# Cluster nodes use real upstream resolvers; never forward their resolver back to LAN DNS.
install -d -m 0700 /etc/rancher/k3s
log 'Host prerequisites installed; no disk has been formatted.'
