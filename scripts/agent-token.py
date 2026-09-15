#!/usr/bin/env python3
"""Obtain an agent access token, or an explicit delegated token, without logging credentials."""
import argparse,json,os,ssl
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request,urlopen
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('actor_file');p.add_argument('--subject-token-file');p.add_argument('--output',required=True)
p.add_argument('--ca',default=str(ROOT/'.local/internal-ca.crt'))
args=p.parse_args()
actor=json.loads(Path(args.actor_file).read_text())
clients=json.loads((ROOT/'.local/identity-clients.json').read_text())
ctx=ssl.create_default_context(cafile=args.ca)
def token(data):
    req=Request('https://auth.admin.internal/application/o/token/',data=urlencode(data).encode(),
                headers={'Content-Type':'application/x-www-form-urlencoded'},method='POST')
    with urlopen(req,context=ctx,timeout=15) as r: return json.load(r)['access_token']
access=token({'grant_type':'client_credentials','client_id':clients['client_id'],
    'username':actor['username'],'password':actor['app_password'],'scope':'openid profile inventory.read'})
if args.subject_token_file:
    access=token({'grant_type':'urn:ietf:params:oauth:grant-type:token-exchange','client_id':clients['client_id'],
        'client_secret':clients['client_secret'],'subject_token':Path(args.subject_token_file).read_text().strip(),
        'subject_token_type':'urn:ietf:params:oauth:token-type:access_token','actor_token':access,
        'actor_token_type':'urn:ietf:params:oauth:token-type:access_token','audience':clients['client_id'],
        'scope':'openid profile inventory.read'})
os.umask(0o077)
with open(args.output,'x') as f: f.write(access+'\n')
print('Access token written to the requested file; lifetime is five minutes.')
