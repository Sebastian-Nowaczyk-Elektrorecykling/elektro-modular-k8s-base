#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname "$0")/lib/common.sh"
[[ $# == 3 ]] || die 'Usage: remove-node.sh NODE_NAME worker|server SSH_TARGET'
node=$1 kind=$2 target=$3
[[ $node =~ ^[a-z0-9]([a-z0-9-]*[a-z0-9])?$ && $kind =~ ^(worker|server)$ && $target != -* ]] || die 'Invalid node, role, or SSH target.'
load_site
tmpdir=$(mktemp -d)
trap 'rm -rf "$tmpdir"' EXIT
kubectl get node "$node" -o json >"$tmpdir/node.json"
python3 - "$tmpdir/node.json" "$kind" "$API_ADDRESS" <<'PY'
import json,sys
n=json.load(open(sys.argv[1])); server='node-role.kubernetes.io/control-plane' in n['metadata']['labels']
assert server==(sys.argv[2]=='server'),'Wrong removal role for node'
assert not any(a['address']==sys.argv[3] for a in n['status']['addresses']), 'Move API_ADDRESS to a surviving endpoint and reconcile/restart clients before removing this node'
PY
if [[ $kind == server ]]; then
    kubectl get nodes -l node-role.kubernetes.io/control-plane -o json >"$tmpdir/servers.json"
    python3 - "$tmpdir/servers.json" "$node" <<'PY'
import json,sys
nodes=json.load(open(sys.argv[1]))['items']; survivors=[n for n in nodes if n['metadata']['name']!=sys.argv[2]]
ready=sum(any(c['type']=='Ready' and c['status']=='True' for c in n['status']['conditions']) for n in survivors)
assert len(nodes)>=3 and ready >= len(nodes)//2+1, 'Removal would lose current etcd quorum; restore health or add a replacement first'
PY
    ssh "$target" sudo k3s etcd-snapshot save
fi
kubectl cordon "$node"
if kubectl -n longhorn-system get nodes.longhorn.io "$node" >/dev/null 2>&1; then
    kubectl -n longhorn-system patch nodes.longhorn.io "$node" --type=merge -p '{"spec":{"allowScheduling":false,"evictionRequested":true}}'
    log 'Waiting up to 30 minutes for Longhorn replicas to leave this node.'
    deadline=$((SECONDS+1800))
    while true; do
        count=$(kubectl -n longhorn-system get replicas.longhorn.io -o json | python3 -c \
            'import json,sys; print(sum(r["spec"].get("nodeID")==sys.argv[1] for r in json.load(sys.stdin)["items"]))' "$node")
        [[ $count -gt 0 ]] || break
        [[ $SECONDS -lt $deadline ]] || die 'Replica eviction did not finish. Node remains cordoned; fix storage capacity/health before retrying.'
        sleep 10
    done
fi
kubectl drain "$node" --ignore-daemonsets --delete-emptydir-data --timeout=30m
service=k3s
[[ $kind == worker ]] && service=k3s-agent
# Fixed remote commands: never interpolate arbitrary shell text from the SSH target.
if [[ $kind == worker ]]; then ssh "$target" sudo systemctl stop k3s-agent; else ssh "$target" sudo systemctl stop k3s; fi
kubectl delete node "$node" --wait=true
if [[ $kind == worker ]]; then ssh "$target" sudo /usr/local/bin/k3s-agent-uninstall.sh; else ssh "$target" sudo /usr/local/bin/k3s-uninstall.sh; fi
log 'Node removed. Retained application disks and Longhorn data require separate deliberate cleanup.'
