"""Expose only OpenFGA Check to application pods; keep the write credential in identity."""
import json
import os
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.error import URLError,HTTPError
from urllib.request import Request,urlopen

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def answer(self,status,data):
        raw=json.dumps(data).encode();self.send_response(status)
        self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)))
        self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        if self.path=='/healthz': return self.answer(200,{'status':'ok'})
        self.answer(404,{'error':'not found'})
    def do_POST(self):
        if self.path!='/check': return self.answer(404,{'error':'not found'})
        try:
            size=int(self.headers.get('Content-Length','0'))
            if size<1 or size>8192: return self.answer(400,{'error':'invalid body length'})
            data=json.loads(self.rfile.read(size))
            key=data['tuple_key']
            if not isinstance(key,dict) or set(key)!={'user','relation','object'} or not all(isinstance(v,str) for v in key.values()):
                return self.answer(400,{'error':'invalid tuple'})
            # Neither callers nor query parameters can change store/model or invoke write APIs.
            body=json.dumps({'tuple_key':key,'authorization_model_id':os.environ['FGA_MODEL_ID'],
                'consistency':'HIGHER_CONSISTENCY'}).encode()
            req=Request('http://openfga:8080/stores/'+os.environ['FGA_STORE_ID']+'/check',data=body,method='POST',
                headers={'Content-Type':'application/json','Authorization':'Bearer '+os.environ['FGA_API_TOKEN']})
            with urlopen(req,timeout=4) as response: result=json.load(response)
            self.answer(200,{'allowed':result.get('allowed') is True})
        except (ValueError,KeyError,TypeError): self.answer(400,{'error':'invalid request'})
        except (HTTPError,URLError,TimeoutError): self.answer(503,{'error':'authorization unavailable'})

if __name__=='__main__': ThreadingHTTPServer(('0.0.0.0',8080),Handler).serve_forever()
