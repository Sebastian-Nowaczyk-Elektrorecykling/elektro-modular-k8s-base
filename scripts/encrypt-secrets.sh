#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname "$0")/lib/common.sh"
cd "$REPO_ROOT"
[[ $# == 1 && $1 == age1* ]] || die 'Usage: encrypt-secrets.sh AGE_PUBLIC_RECIPIENT'
[[ -s .local/bootstrap-secrets.yaml ]] || die 'Generate bootstrap secrets first.'
mkdir -p clusters/lan/secrets
sops --encrypt --age "$1" --encrypted-regex '^(data|stringData)$' --input-type yaml --output-type yaml \
    .local/bootstrap-secrets.yaml >clusters/lan/secrets/bootstrap.sops.yaml
cat >clusters/lan/secrets/kustomization.yaml <<'EOF'
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - bootstrap.sops.yaml
EOF
cat >clusters/lan/secrets-sync.yaml <<'EOF'
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: secrets
  namespace: flux-system
spec:
  interval: 10m
  dependsOn:
    - name: namespaces
  sourceRef:
    kind: GitRepository
    name: cluster
  path: ./clusters/lan/secrets
  prune: false
  decryption:
    provider: sops
    secretRef:
      name: sops-age
EOF
python3 - <<'PY'
from pathlib import Path
import yaml
p=Path('clusters/lan/kustomization.yaml'); d=yaml.safe_load(p.read_text())
if 'secrets-sync.yaml' not in d['resources']: d['resources'].append('secrets-sync.yaml')
p.write_text(yaml.safe_dump(d,sort_keys=False))
PY
log 'Encrypted secrets are ready to commit. Install your age private key in flux-system/sops-age before reconciliation.'
