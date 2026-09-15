#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname "$0")/lib/common.sh"
cd "$REPO_ROOT"
umask 077
mkdir -p .local
kubectl -n identity rollout status deployment/authentik-worker --timeout=15m
kubectl -n identity exec -i deployment/authentik-worker -- ak shell -c 'exec(__import__("sys").stdin.read())' \
    <scripts/identity-bootstrap.py >.local/identity-bootstrap.out
python3 - <<'PY'
import json,yaml
from pathlib import Path
lines=Path('.local/identity-bootstrap.out').read_text().splitlines()
data=json.loads(next(x.split('=',1)[1] for x in lines if x.startswith('ELEKTRO_CREDENTIALS=')))
Path('.local/identity-clients.json').write_text(json.dumps(data,indent=2)+'\n')
manifest=dict(apiVersion='v1',kind='Secret',metadata=dict(name='inventory-oidc',namespace='apps'),type='Opaque',stringData={
    'OIDC_CLIENT_ID':data['client_id'],'OIDC_CLIENT_SECRET':data['client_secret'],
    'OIDC_AUDIENCES':data['client_id']+','+data['cli_client_id']})
Path('.local/inventory-oidc.yaml').write_text(yaml.safe_dump(manifest,sort_keys=False))
PY
kubectl apply -f .local/inventory-oidc.yaml
log 'Inventory providers configured with empty access groups. Credentials saved privately under .local/.'
