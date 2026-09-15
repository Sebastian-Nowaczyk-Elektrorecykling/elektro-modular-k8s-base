#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname "$0")/lib/common.sh"
usage() { log 'Usage: install-node.sh controller|worker|hybrid bootstrap|join NODE_NAME NODE_IPV4 [TOKEN_FILE]'; }
[[ $# -ge 4 && $# -le 5 ]] || { usage; exit 2; }
role=$1 mode=$2 node_name=$3 node_ip=$4 token_file=${5:-}
[[ $role =~ ^(controller|worker|hybrid)$ && $mode =~ ^(bootstrap|join)$ ]] || { usage; exit 2; }
[[ $role != worker || $mode == join ]] || die 'A worker cannot bootstrap the control plane.'
[[ $node_name =~ ^[a-z0-9]([a-z0-9-]*[a-z0-9])?$ ]] || die 'NODE_NAME must be a lowercase DNS label.'
root_required
debian_required
load_site
fresh_node_required
python3 - "$node_ip" "$LAN_CIDR" <<'PY'
import ipaddress,sys
ip=ipaddress.ip_address(sys.argv[1]); net=ipaddress.ip_network(sys.argv[2])
assert ip.version==4 and ip in net and ip not in (net.network_address,net.broadcast_address), 'Invalid node address'
PY
ip -j address show | python3 -c 'import sys,json; ip=sys.argv[1]; assert any(x.get("local")==ip for a in json.load(sys.stdin) for x in a["addr_info"]), "Set a stable node IP on the LAN interface first"' "$node_ip"
if [[ $mode == join ]]; then
    [[ -n $token_file && -s $token_file ]] || die 'Join requires a file containing the k3s secure join token.'
    [[ $(head -c 3 "$token_file") == K10 ]] || die 'Use the secure K10... token copied from an existing server.'
fi
bash "$REPO_ROOT/scripts/prepare-node.sh"
if [[ $role != controller ]]; then bash "$REPO_ROOT/scripts/prepare-gpu.sh"; fi
hostnamectl set-hostname "$node_name.internal"
printf '%s %s.internal %s\n' "$node_ip" "$node_name" "$node_name" >>/etc/hosts
printf '%s\n' "$DNS_UPSTREAMS" | tr ' ' '\n' | sed 's/^/nameserver /' >/etc/rancher/k3s/resolv.conf
if [[ $mode == join ]]; then install -m 0600 "$token_file" /etc/rancher/k3s/join-token; fi
export ELEKTRO_ROLE=$role ELEKTRO_MODE=$mode ELEKTRO_NODE_NAME=$node_name ELEKTRO_NODE_IP=$node_ip
export API_ADDRESS POD_CIDR SERVICE_CIDR CLUSTER_DNS
python3 - <<'PY'
import os,yaml
e=os.environ
role=e['ELEKTRO_ROLE']; server=role!='worker'
c={'node-name':e['ELEKTRO_NODE_NAME'],'node-ip':e['ELEKTRO_NODE_IP'],'resolv-conf':'/etc/rancher/k3s/resolv.conf',
   'node-label':['elektro.internal/workload='+str(role!='controller').lower(),'elektro.internal/gateway='+str(server).lower()]}
if role!='controller':
    c['node-label'].append('node.longhorn.io/create-default-disk=true')
if e['ELEKTRO_MODE']=='join':
    c.update({'server':'https://'+e['API_ADDRESS']+':6443','token-file':'/etc/rancher/k3s/join-token'})
elif server: c['cluster-init']=True
if server:
    c.update({'disable':['traefik','servicelb','local-storage'],'flannel-backend':'none','disable-network-policy':True,
              'disable-kube-proxy':True,'cluster-cidr':e['POD_CIDR'],'service-cidr':e['SERVICE_CIDR'],
              'cluster-dns':e['CLUSTER_DNS'],'tls-san':[e['API_ADDRESS'],'api.admin.internal'],
              'write-kubeconfig-mode':'0600','secrets-encryption':True,
              'etcd-snapshot-schedule-cron':'0 */6 * * *','etcd-snapshot-retention':14})
if role=='controller': c['node-taint']=['node-role.kubernetes.io/control-plane=true:NoSchedule']
with open('/etc/rancher/k3s/config.yaml','w') as f: yaml.safe_dump(c,f)
PY
chmod 0600 /etc/rancher/k3s/config.yaml
# Use the installer from the pinned release tag, not an unversioned curl|sh stream.
tmpdir=$(mktemp -d)
trap 'rm -rf "$tmpdir"' EXIT
download "https://raw.githubusercontent.com/k3s-io/k3s/$K3S_VERSION/install.sh" "$tmpdir/install.sh"
kind=server
[[ $role == worker ]] && kind=agent
INSTALL_K3S_VERSION=$K3S_VERSION INSTALL_K3S_EXEC=$kind sh "$tmpdir/install.sh"
log 'k3s installed. Before Cilium is bootstrapped, NotReady is expected. Reboot worker/hybrid nodes for GPU drivers.'
