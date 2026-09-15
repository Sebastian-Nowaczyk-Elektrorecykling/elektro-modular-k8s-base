"""Real authentik token-exchange and OpenFGA model contracts (CI containers only)."""
import json,sys,time
from pathlib import Path
from urllib.error import HTTPError,URLError
from urllib.parse import urlencode
from urllib.request import Request,urlopen
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'apps/inventory'))
from authz import authorize,Denied

def result(path,prefix):
    return json.loads(next(x.split('=',1)[1] for x in path.read_text().splitlines() if x.startswith(prefix+'=')))
client=result(ROOT/'.local/ci-identity.out','ELEKTRO_CREDENTIALS')
users=result(ROOT/'.local/ci-fixture.out','ELEKTRO_FIXTURE')

def post(base,path,data,form=False):
    body=urlencode(data).encode() if form else json.dumps(data).encode()
    req=Request(base+path,data=body,headers={'Content-Type':'application/x-www-form-urlencoded' if form else 'application/json'})
    with urlopen(req,timeout=10) as r:return json.load(r)
AK='http://127.0.0.1:19000'
def token(name):
    u=users[name]
    return post(AK,'/application/o/token/',{'client_id':client['client_id'],'grant_type':'client_credentials',
        'username':u['username'],'password':u['app_password'],'scope':'openid profile inventory.read'},True)['access_token']
tokens={n:token(n) for n in users}
def exchange(subject,actor=None):
    d={'grant_type':'urn:ietf:params:oauth:grant-type:token-exchange','client_id':client['client_id'],
        'client_secret':client['client_secret'],'subject_token':tokens[subject],
        'subject_token_type':'urn:ietf:params:oauth:token-type:access_token','scope':'openid profile inventory.read'}
    if actor:d.update(actor_token=tokens[actor],actor_token_type='urn:ietf:params:oauth:token-type:access_token')
    return post(AK,'/application/o/token/',d,True)['access_token']
def introspect(access):
    return post(AK,'/application/o/introspect/',{'client_id':client['client_id'],'client_secret':client['client_secret'],'token':access},True)
delegated=introspect(exchange('ci-user','ci-agent'))
assert delegated['sub']==users['ci-user']['uuid'] and delegated['act']['sub']==users['ci-agent']['uuid']
agent_child=introspect(exchange('ci-agent','ci-child'))
assert agent_child['sub']==users['ci-agent']['uuid'] and agent_child['act']['sub']==users['ci-child']['uuid']
assert introspect(tokens['ci-independent'])['active'] is True
for subject,actor in [('ci-user',None),('ci-independent','ci-agent')]:
    try:exchange(subject,actor)
    except HTTPError as e:assert e.code in (400,403)
    else:raise AssertionError('Unattributed or wrong-parent exchange was accepted')
for _ in range(50):
    try:
        store=post('http://127.0.0.1:18080','/stores',{'name':'contract-test'});break
    except URLError:time.sleep(.2)
else:raise AssertionError('OpenFGA did not start')
base='/stores/'+store['id']
model=post('http://127.0.0.1:18080',base+'/authorization-models',json.loads((ROOT/'platform/openfga/model.json').read_text()))['authorization_model_id']
def check(user,relation,obj):
    return post('http://127.0.0.1:18080',base+'/check',{'authorization_model_id':model,
        'tuple_key':dict(user=user,relation=relation,object=obj),'consistency':'HIGHER_CONSISTENCY'})['allowed']
sub=users['ci-user']['uuid'];actor=users['ci-agent']['uuid']
tuples=[dict(user='principal:'+sub,relation='member',object='service:inventory'),
    dict(user='principal:'+actor,relation='member',object='service:inventory'),
    dict(user='principal:'+actor,relation='delegate',object='delegation:inventory/'+sub),
    dict(user='service:inventory',relation='target',object='delegation:inventory/'+sub)]
for count in (0,2,4):
    if count:
        post('http://127.0.0.1:18080',base+'/write',{'authorization_model_id':model,'writes':{'tuple_keys':tuples[count-2:count]}})
    try:result=authorize(delegated,AK+'/application/o/inventory/',[client['client_id']],check)
    except Denied:assert count!=4
    else:assert count==4 and result['actor']==actor
post('http://127.0.0.1:18080',base+'/write',{'authorization_model_id':model,'deletes':{'tuple_keys':[tuples[2]]}})
try:authorize(delegated,AK+'/application/o/inventory/',[client['client_id']],check)
except Denied:pass
else:raise AssertionError('Revoked delegation was accepted')
print('Live contracts passed: provider setup, independent agent, user-to-agent, agent-to-agent, explicit actor requirement, OpenFGA denial/grant/revocation.')
