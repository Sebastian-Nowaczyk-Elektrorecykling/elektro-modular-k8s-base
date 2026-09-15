#!/usr/bin/env python3
"""Initialize the OpenFGA model or change explicit service/delegation tuples."""
import argparse
import base64
import json
import os
import re
import socket
import subprocess
import time
from pathlib import Path
from urllib.request import Request,urlopen
import yaml

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
sub=parser.add_subparsers(dest='command',required=True)
sub.add_parser('init')
for name in ('grant','revoke'):
    p=sub.add_parser(name);p.add_argument('subject');p.add_argument('service')
for name in ('delegate','undelegate'):
    p=sub.add_parser(name);p.add_argument('actor');p.add_argument('subject');p.add_argument('service')
args=parser.parse_args()
if args.command!='init':
    import uuid
    for name in ('subject','actor'):
        if hasattr(args,name): uuid.UUID(getattr(args,name))
    if not re.fullmatch('[a-z][a-z0-9-]{0,60}',args.service): parser.error('Invalid service name')
os.umask(0o077)
local=ROOT/'.local';local.mkdir(mode=0o700,exist_ok=True)
secret=json.loads(subprocess.check_output(['kubectl','-n','identity','get','secret','openfga-config','-o','json']))
token=base64.b64decode(secret['data']['api-token']).decode()
port=18080
with socket.socket() as sock:
    if sock.connect_ex(('127.0.0.1',port))==0: raise SystemExit('Port 18080 is already in use; stop the existing process first')
process=subprocess.Popen(['kubectl','-n','identity','port-forward','--address=127.0.0.1','service/openfga',f'{port}:8080'],
    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

def request(path,data=None):
    body=json.dumps(data).encode() if data is not None else None
    with urlopen(Request(f'http://127.0.0.1:{port}'+path,data=body,
        headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'},method='POST' if data is not None else 'GET'),timeout=10) as r:
        return json.load(r) if r.status!=204 else {}

def apply_secret(name,namespace,data):
    manifest=dict(apiVersion='v1',kind='Secret',metadata=dict(name=name,namespace=namespace),type='Opaque',stringData=data)
    subprocess.run(['kubectl','apply','-f','-'],input=yaml.safe_dump(manifest),text=True,check=True)

try:
    for _ in range(100):
        if process.poll() is not None: raise RuntimeError('OpenFGA port-forward failed')
        with socket.socket() as sock:
            if sock.connect_ex(('127.0.0.1',port))==0: break
        time.sleep(.1)
    else: raise RuntimeError('OpenFGA port-forward timed out')
    state_path=local/'fga-state.json'
    if args.command=='init':
        if state_path.exists():
            state=json.loads(state_path.read_text())
            request('/stores/'+state['store_id']+'/authorization-models/'+state['model_id'])
        else:
            # Recover stable IDs after workstation loss before ever creating a second store.
            stores=request('/stores?page_size=100')['stores']
            existing=[x for x in stores if x['name']=='elektro-platform']
            if existing: raise RuntimeError('Existing elektro-platform store found. Restore .local/fga-state.json from its store/model IDs; never silently replace access policy')
            store=request('/stores',{'name':'elektro-platform'})
            model=request('/stores/'+store['id']+'/authorization-models',json.loads((ROOT/'platform/openfga/model.json').read_text()))
            state={'store_id':store['id'],'model_id':model['authorization_model_id']}
            state_path.write_text(json.dumps(state,indent=2)+'\n')
        apply_secret('openfga-check-config','identity',{'FGA_STORE_ID':state['store_id'],'FGA_MODEL_ID':state['model_id']})
        print('OpenFGA store/model ready; no default access tuples were created.')
    else:
        state=json.loads(state_path.read_text());base='/stores/'+state['store_id']
        def change(key,delete=False):
            exists=bool(request(base+'/read',{'tuple_key':key,'page_size':1}).get('tuples'))
            if exists==delete:
                request(base+'/write',{'authorization_model_id':state['model_id'],
                    'deletes' if delete else 'writes':{'tuple_keys':[key]}})
        if args.command in ('grant','revoke'):
            change({'user':'principal:'+args.subject,'relation':'member','object':'service:'+args.service},args.command=='revoke')
        else:
            obj='delegation:'+args.service+'/'+args.subject
            change({'user':'principal:'+args.actor,'relation':'delegate','object':obj},args.command=='undelegate')
            if args.command=='delegate': change({'user':'service:'+args.service,'relation':'target','object':obj})
        print('Requested access tuple state applied.')
finally:
    process.terminate()
    try: process.wait(timeout=5)
    except subprocess.TimeoutExpired: process.kill();process.wait()
