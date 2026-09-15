#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
mkdir -p .local
umask 077
python3 - <<'PY'
import secrets
from pathlib import Path
Path('.local/ci.env').write_text('AUTHENTIK_SECRET_KEY='+secrets.token_hex(48)+'\n'+
    'AUTHENTIK_POSTGRESQL__HOST=ci-postgres\nAUTHENTIK_POSTGRESQL__NAME=authentik\n'+
    'AUTHENTIK_POSTGRESQL__USER=postgres\nAUTHENTIK_POSTGRESQL__PASSWORD='+secrets.token_hex(32)+'\n'+
    'AUTHENTIK_BOOTSTRAP_PASSWORD='+secrets.token_urlsafe(32)+'\nAUTHENTIK_BOOTSTRAP_EMAIL=ci@example.invalid\n')
PY
cleanup() { docker rm -f ci-server ci-worker ci-postgres ci-fga >/dev/null 2>&1 || true; docker network rm elektro-ci >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker network create elektro-ci >/dev/null
python3 - <<'PY'
from pathlib import Path
e=dict(x.split('=',1) for x in Path('.local/ci.env').read_text().splitlines())
Path('.local/postgres.env').write_text('POSTGRES_DB=authentik\nPOSTGRES_PASSWORD='+e['AUTHENTIK_POSTGRESQL__PASSWORD']+'\n')
PY
docker run -d --name ci-postgres --network elektro-ci --env-file .local/postgres.env postgres:17.11 >/dev/null
for _ in $(seq 1 60); do
    if docker exec ci-postgres pg_isready -U postgres >/dev/null 2>&1; then break; fi
    sleep 2
done
docker run -d --name ci-server --network elektro-ci --env-file .local/ci.env \
    -p 127.0.0.1:19000:9000 ghcr.io/goauthentik/server:2026.8.2 server >/dev/null
docker run -d --name ci-worker --network elektro-ci --env-file .local/ci.env \
    -v "$PWD/platform/identity-config/platform.yaml:/blueprints/elektro/platform.yaml:ro" \
    ghcr.io/goauthentik/server:2026.8.2 worker >/dev/null
ready=false
for _ in $(seq 1 120); do
    if curl --fail --silent http://127.0.0.1:19000/-/health/ready/ >/dev/null; then ready=true; break; fi
    sleep 3
done
[[ $ready == true ]] || { printf 'authentik did not become ready\n' >&2; exit 1; }
ready=false
for _ in $(seq 1 30); do
    if docker exec -i ci-worker ak shell -c 'exec(__import__("sys").stdin.read())' <scripts/identity-bootstrap.py >.local/ci-identity.out 2>.local/ci-identity.err; then ready=true; break; fi
    sleep 3
done
[[ $ready == true ]] || { cat .local/ci-identity.err >&2; exit 1; }
docker exec -i ci-worker ak shell -c 'exec(__import__("sys").stdin.read())' <tests/identity_fixture.py >.local/ci-fixture.out
docker run -d --name ci-fga -p 127.0.0.1:18080:8080 openfga/openfga:v1.20.0 run --datastore-engine memory --playground-enabled=false >/dev/null
python3 tests/live_identity.py
