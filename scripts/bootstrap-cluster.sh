#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname "$0")/lib/common.sh"
load_site
cd "$REPO_ROOT"
for tool in kubectl helm flux python3; do command -v "$tool" >/dev/null || die "Missing $tool; run admin-workstation.sh."; done
[[ -s .local/bootstrap-secrets.yaml ]] || die 'Run scripts/generate-secrets.py first.'
kubectl get --raw=/readyz >/dev/null
log 'Installing Gateway API CRDs and the bootstrap CNI. This Helm release is later adopted by Flux.'
kubectl apply --server-side -k infrastructure/gateway-api
helm repo add cilium https://helm.cilium.io/ --force-update
helm repo update cilium
helm upgrade --install cilium cilium/cilium --namespace kube-system --version "$CILIUM_VERSION" -f .local/cilium-values.yaml
kubectl -n kube-system rollout status daemonset/cilium --timeout=10m
kubectl -n kube-system rollout status deployment/cilium-operator --timeout=10m
workers=$(kubectl get nodes -l elektro.internal/workload=true -o name | wc -l)
[[ $workers -gt 0 ]] || die 'Join at least one worker/hybrid before installing Flux and platform workloads.'
kubectl apply -k infrastructure/namespaces
kubectl apply -f .local/bootstrap-secrets.yaml
flux check --pre
flux install --version="v$FLUX_VERSION" --export >.local/flux-install.yaml
python3 - <<'PY'
import yaml
from pathlib import Path
p=Path('.local/flux-install.yaml'); docs=list(yaml.safe_load_all(p.read_text()))
for d in docs:
    if d and d.get('kind')=='Deployment':
        spec=d['spec']['template']['spec']
        spec.setdefault('nodeSelector',{})['elektro.internal/workload']='true'
        if d['metadata']['name']=='kustomize-controller':
            spec['containers'][0]['args'].append('--feature-gates=StrictPostBuildSubstitutions=true')
p.write_text(yaml.safe_dump_all(docs,sort_keys=False))
PY
kubectl apply --server-side -f .local/flux-install.yaml
kubectl -n flux-system rollout status deployment/source-controller --timeout=5m
kubectl -n flux-system rollout status deployment/kustomize-controller --timeout=5m
kubectl -n flux-system rollout status deployment/helm-controller --timeout=5m
kubectl apply -k bootstrap
flux reconcile source git cluster
flux reconcile kustomization cluster --with-source
log 'Flux now reconciles the repository. Run flux get kustomizations -A; follow docs/bootstrap.md for identity and access setup.'
