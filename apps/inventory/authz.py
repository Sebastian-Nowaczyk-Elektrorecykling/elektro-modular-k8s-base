"""Authorization reference implementation. Token validation stays with the identity provider."""
import re
import time
UUID=re.compile(r'^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$')

class Denied(Exception):
    pass

def authorize(claims, issuer, audiences, check, now=None):
    now=time.time() if now is None else now
    if claims.get('active') is not True or claims.get('iss')!=issuer:
        raise Denied('inactive token or wrong issuer')
    exp=claims.get('exp')
    if isinstance(exp,bool) or not isinstance(exp,(float,int)) or exp<=now:
        raise Denied('expired token')
    if claims.get('nbf',0)>now:
        raise Denied('token is not yet valid')
    aud=claims.get('aud',[]);aud=[aud] if isinstance(aud,str) else aud
    if not isinstance(aud,list) or not any(a in audiences for a in aud):
        raise Denied('wrong audience')
    if 'inventory.read' not in claims.get('scope','').split():
        raise Denied('missing inventory.read scope')
    subject=claims.get('sub','')
    if not isinstance(subject,str) or not UUID.fullmatch(subject):
        raise Denied('subject must be an immutable user UUID')
    if not check('principal:'+subject,'can_access','service:inventory'):
        raise Denied('subject has no service grant')
    actor_claim=claims.get('act')
    if actor_claim is None:
        return {'subject':subject,'actor':None}
    # The pinned issuer records one immediate actor. Do not silently flatten an unsupported chain.
    if not isinstance(actor_claim,dict) or 'act' in actor_claim:
        raise Denied('unsupported actor chain')
    actor=actor_claim.get('sub','')
    if not isinstance(actor,str) or not UUID.fullmatch(actor) or actor==subject:
        raise Denied('invalid actor')
    if actor_claim.get('iss',issuer)!=issuer:
        raise Denied('wrong actor issuer')
    if not check('principal:'+actor,'can_access','service:inventory'):
        raise Denied('actor has no service grant')
    if not check('principal:'+actor,'can_act','delegation:inventory/'+subject):
        raise Denied('delegation has not been granted')
    return {'subject':subject,'actor':actor}
