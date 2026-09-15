import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps/inventory'))
from authz import authorize,Denied
SUB='11111111-1111-1111-1111-111111111111'
ACT='22222222-2222-2222-2222-222222222222'
ISS='https://auth.admin.internal/application/o/inventory/'

class Authorization(unittest.TestCase):
    def setUp(self):
        self.claims=dict(active=True,iss=ISS,aud=['inventory'],sub=SUB,exp=200,scope='openid inventory.read')
        self.grants={('principal:'+SUB,'can_access','service:inventory')}
    def call(self):return authorize(self.claims,ISS,['inventory'],lambda *k:k in self.grants,now=100)
    def delegate(self):
        self.claims['act']={'sub':ACT}
        self.grants.add(('principal:'+ACT,'can_access','service:inventory'))
        self.grants.add(('principal:'+ACT,'can_act','delegation:inventory/'+SUB))
    def test_human_or_autonomous_agent(self):self.assertIsNone(self.call()['actor'])
    def test_explicit_delegation(self):self.delegate();self.assertEqual(self.call()['actor'],ACT)
    def test_subject_grant_required(self):
        self.delegate();self.grants.remove(('principal:'+SUB,'can_access','service:inventory'))
        with self.assertRaises(Denied):self.call()
    def test_actor_grant_required(self):
        self.delegate();self.grants.remove(('principal:'+ACT,'can_access','service:inventory'))
        with self.assertRaises(Denied):self.call()
    def test_delegation_grant_required(self):
        self.claims['act']={'sub':ACT};self.grants.add(('principal:'+ACT,'can_access','service:inventory'))
        with self.assertRaises(Denied):self.call()
    def test_revoked_delegation(self):
        self.delegate();self.call();self.grants.remove(('principal:'+ACT,'can_act','delegation:inventory/'+SUB))
        with self.assertRaises(Denied):self.call()
    def test_wrong_service_audience(self):
        self.claims['aud']='payroll'
        with self.assertRaises(Denied):self.call()
    def test_wrong_issuer(self):
        self.claims['iss']='https://attacker.invalid'
        with self.assertRaises(Denied):self.call()
    def test_expired(self):
        self.claims['exp']=99
        with self.assertRaises(Denied):self.call()
    def test_missing_scope(self):
        self.claims['scope']='openid'
        with self.assertRaises(Denied):self.call()
    def test_inactive(self):
        self.claims['active']=False
        with self.assertRaises(Denied):self.call()
    def test_nested_chain_is_not_silently_flattened(self):
        self.delegate();self.claims['act']['act']={'sub':SUB}
        with self.assertRaises(Denied):self.call()
    def test_cross_subject_delegation_is_denied(self):
        self.delegate();self.claims['sub']='33333333-3333-3333-3333-333333333333'
        self.grants.add(('principal:'+self.claims['sub'],'can_access','service:inventory'))
        with self.assertRaises(Denied):self.call()
    def test_fga_failure_does_not_allow(self):
        def broken(*_):raise TimeoutError('unavailable')
        with self.assertRaises(TimeoutError):authorize(self.claims,ISS,['inventory'],broken,now=100)
