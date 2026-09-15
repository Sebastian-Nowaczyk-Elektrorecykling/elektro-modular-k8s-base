#!/usr/bin/env python3
"""Interactive authorization-code + PKCE example for the public inventory CLI."""
import argparse,base64,hashlib,json,os,secrets,ssl,webbrowser
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
from urllib.parse import parse_qs,urlencode,urlparse
from urllib.request import Request,urlopen
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True)
p.add_argument('--ca',default=str(ROOT/'.local/internal-ca.crt'));args=p.parse_args()
state=secrets.token_urlsafe(32);verifier=secrets.token_urlsafe(48)
challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
result={}
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_GET(self):
        data=parse_qs(urlparse(self.path).query)
        valid=urlparse(self.path).path=='/callback' and data.get('state')==[state] and 'code' in data
        self.send_response(200 if valid else 400);self.end_headers()
        if valid:
            result['code']=data['code'][0];self.wfile.write(b'Sign-in complete. Return to your terminal.')
        else: self.wfile.write(b'Invalid callback.')
server=HTTPServer(('127.0.0.1',8765),Handler);server.timeout=180
query={'client_id':'inventory-cli','response_type':'code','redirect_uri':'http://localhost:8765/callback',
    'scope':'openid profile inventory.read','state':state,'code_challenge':challenge,'code_challenge_method':'S256'}
url='https://auth.admin.internal/application/o/authorize/?'+urlencode(query)
print('Open this sign-in URL on this workstation: '+url);webbrowser.open(url)
server.handle_request();server.server_close()
if 'code' not in result: raise SystemExit('Sign-in did not complete; try again')
query={'grant_type':'authorization_code','client_id':'inventory-cli','code':result['code'],'code_verifier':verifier,
    'redirect_uri':'http://localhost:8765/callback'}
with urlopen(Request('https://auth.admin.internal/application/o/token/',data=urlencode(query).encode(),
    headers={'Content-Type':'application/x-www-form-urlencoded'}),context=ssl.create_default_context(cafile=args.ca),timeout=15) as r:
    token=json.load(r)['access_token']
os.umask(0o077)
with open(args.output,'x') as f: f.write(token+'\n')
print('Access token written to the requested file.')
