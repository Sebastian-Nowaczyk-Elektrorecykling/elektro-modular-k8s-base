#!/usr/bin/env python3
"""Small read-only API demonstrating bearer authentication and OpenFGA delegation checks."""
import base64
import json
import os
import ssl
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.error import HTTPError,URLError
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from authz import Denied,authorize

ISSUER='https://auth.admin.internal/application/o/inventory/'
CLI_ISSUER='https://auth.admin.internal/application/o/inventory-cli/'
CTX=ssl.create_default_context(cafile='/trust/ca.crt')

def post(url,body,headers):
    with urlopen(Request(url,data=body,headers=headers,method='POST'),context=CTX,timeout=4) as r:
        return json.load(r)

def check(user,relation,obj):
    result=post(os.environ['FGA_URL']+'/check',
        json.dumps({'tuple_key':{'user':user,'relation':relation,'object':obj}}).encode(),
        {'Content-Type':'application/json'})
    return result.get('allowed') is True

class Handler(BaseHTTPRequestHandler):
    def log_message(self,fmt,*args):
        # Do not log headers, URL query strings, tokens, or authentication bodies.
        pass
    def answer(self,status,data):
        raw=json.dumps(data).encode();self.send_response(status)
        self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        if self.path=='/healthz': return self.answer(200,{'status':'ok'})
        if self.path!='/': return self.answer(404,{'error':'not found'})
        value=self.headers.get('Authorization','')
        if not value.startswith('Bearer '): return self.answer(401,{'error':'bearer token required'})
        token=value[7:]
        # Authentik also introspects opaque refresh tokens; those must never authorize API requests.
        if len(token)>16384 or token.count('.')!=2: return self.answer(401,{'error':'access JWT required'})
        try:
            credentials=(os.environ['OIDC_CLIENT_ID']+':'+os.environ['OIDC_CLIENT_SECRET']).encode()
            claims=post('https://auth.admin.internal/application/o/introspect/',urlencode({'token':token}).encode(),
                {'Content-Type':'application/x-www-form-urlencoded','Authorization':'Basic '+base64.b64encode(credentials).decode()})
            issuer=claims.get('iss')
            if issuer not in (ISSUER,CLI_ISSUER): raise Denied('untrusted issuer')
            # Delegated tokens are issued by the confidential inventory provider only.
            if issuer==CLI_ISSUER and claims.get('act') is not None: raise Denied('unexpected CLI delegation')
            principal=authorize(claims,issuer,os.environ['OIDC_AUDIENCES'].split(','),check)
            self.answer(200,dict(service='inventory',**principal))
        except Denied:
            self.answer(403,{'error':'access denied'})
        except (HTTPError,URLError,TimeoutError,ValueError,KeyError,TypeError):
            self.answer(503,{'error':'identity or authorization service unavailable'})

if __name__=='__main__':
    ThreadingHTTPServer(('0.0.0.0',8080),Handler).serve_forever()
