#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname "$0")/lib/common.sh"
[[ $# == 3 ]] || die 'Usage: configure-network.sh INTERFACE NODE_IP LAN_ROUTER (run from the local console)'
root_required
debian_required
load_site
iface=$1 node_ip=$2 router=$3
[[ $iface =~ ^[a-zA-Z0-9_.:-]+$ && -d /sys/class/net/$iface ]] || die 'Unknown interface.'
prefix=$(python3 - "$LAN_CIDR" "$node_ip" "$router" <<'PY'
import ipaddress,sys
net=ipaddress.ip_network(sys.argv[1])
for value in sys.argv[2:]:
    address=ipaddress.ip_address(value)
    assert address in net and address not in (net.network_address,net.broadcast_address),'Address outside LAN'
print(net.prefixlen)
PY
)
apt-get update
apt-get install -y systemd-resolved
mkdir -p /etc/systemd/network
cat >"/etc/systemd/network/10-elektro-$iface.network" <<EOF
[Match]
Name=$iface

[Network]
Address=$node_ip/$prefix
Gateway=$router
DNS=$DNS_UPSTREAMS
Domains=internal
IPv6AcceptRA=no
EOF
systemctl disable --now NetworkManager.service 2>/dev/null || true
systemctl disable --now networking.service 2>/dev/null || true
systemctl enable --now systemd-networkd systemd-resolved
ln -sf /run/systemd/resolve/resolv.conf /etc/resolv.conf
networkctl reload
networkctl reconfigure "$iface"
log 'Static host network configured. Ensure the address cannot be leased to another LAN device.'
