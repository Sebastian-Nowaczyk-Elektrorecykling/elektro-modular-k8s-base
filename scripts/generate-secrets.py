#!/usr/bin/env python3
"""Create unique bootstrap secrets locally. Never overwrites an existing set."""
import os
import secrets
import subprocess
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[1]

def secret(name,namespace,data,typ='Opaque'):
    return dict(apiVersion='v1',kind='Secret',metadata=dict(name=name,namespace=namespace),type=typ,stringData=data)

def main():
    os.umask(0o077)
    local=ROOT/'.local'; local.mkdir(mode=0o700,exist_ok=True)
    target=local/'bootstrap-secrets.yaml'
    if target.exists():
        raise SystemExit('Existing bootstrap-secrets.yaml preserved. Follow the rotation runbook to change credentials.')
    key=local/'internal-ca.key'; cert=local/'internal-ca.crt'
    if key.exists() or cert.exists():
        raise SystemExit('Existing CA material found; inspect the previous attempt instead of replacing trust.')
    subprocess.run(['openssl','req','-x509','-newkey','rsa:4096','-sha256','-nodes','-days','3650',
        '-subj','/CN=Elektro Internal Root CA', '-addext','basicConstraints=critical,CA:TRUE',
        '-addext','keyUsage=critical,keyCertSign,cRLSign','-keyout',str(key),'-out',str(cert)],check=True,capture_output=True)
    documents=[secret('internal-ca','cert-manager',{'tls.crt':cert.read_text(),'tls.key':key.read_text()},'kubernetes.io/tls'),
               secret('internal-ca-trust','apps',{'ca.crt':cert.read_text()})]
    for name in ('authentik','openfga'):
        password=secrets.token_hex(32)
        documents.append(secret(name+'-db-app','identity',dict(username=name,password=password),'kubernetes.io/basic-auth'))
        if name=='openfga':
            uri=f'postgres://openfga:{password}@openfga-db-rw.identity.svc.cluster.local:5432/openfga?sslmode=verify-full&sslrootcert=/db-ca/ca.crt'
            documents.append(secret('openfga-config','identity',{'datastore-uri':uri,'api-token':secrets.token_hex(32)}))
    documents.append(secret('authentik-secrets','identity',dict(AUTHENTIK_SECRET_KEY=secrets.token_hex(48),
        AUTHENTIK_BOOTSTRAP_PASSWORD=secrets.token_urlsafe(32),AUTHENTIK_BOOTSTRAP_TOKEN=secrets.token_hex(32),
        AUTHENTIK_BOOTSTRAP_EMAIL='admin@admin.internal')))
    target.write_text(yaml.safe_dump_all(documents,sort_keys=False))
    print('Created .local/bootstrap-secrets.yaml and the private CA. Back these up securely before bootstrap.')

if __name__=='__main__': main()
