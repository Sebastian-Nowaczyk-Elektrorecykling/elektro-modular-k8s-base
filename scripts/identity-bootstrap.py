"""Executed inside the pinned authentik worker by configure-identity.sh."""
import json
import secrets
from authentik.core.models import Application, Group
from authentik.crypto.models import CertificateKeyPair
from authentik.flows.models import Flow
from authentik.policies.models import PolicyBinding
from authentik.policies.expression.models import ExpressionPolicy
from authentik.providers.oauth2.models import OAuth2Provider, ScopeMapping, RedirectURI, RedirectURIMatchingMode

authorize=Flow.objects.get(slug='default-provider-authorization-explicit-consent')
invalidate=Flow.objects.get(slug='default-provider-invalidation-flow')
signing_key=CertificateKeyPair.objects.filter(managed='goauthentik.io/crypto/jwt').first()
if signing_key is None:
    signing_key=CertificateKeyPair.objects.filter(name='authentik Self-signed Certificate').first()
if signing_key is None:
    raise RuntimeError('Default signing certificate not ready; allow default blueprints to finish first')
scope,_=ScopeMapping.objects.update_or_create(name='Elektro inventory read',defaults={
    'scope_name':'inventory.read','expression':'return {}'})
group,_=Group.objects.get_or_create(name='service-inventory')
delegation_policy,_=ExpressionPolicy.objects.update_or_create(name='Elektro require explicit actor',defaults={
    'expression':'''if request.context.get("oauth_grant_type") == "urn:ietf:params:oauth:grant-type:token-exchange":
    return bool(request.http_request.POST.get("actor_token")) and bool(request.http_request.POST.get("actor_token_type"))
return True''', 'execution_logging':False})
providers={}
for slug,client_type in [('inventory','confidential'),('inventory-cli','public')]:
    defaults=dict(authorization_flow=authorize,invalidation_flow=invalidate,client_type=client_type,
        sub_mode='user_uuid',issuer_mode='per_provider',signing_key=signing_key,
        access_token_validity='minutes=5',include_claims_in_id_token=True,
        redirect_uris=[RedirectURI(RedirectURIMatchingMode.STRICT,'http://localhost:8765/callback')],
        grant_types=['authorization_code'] if client_type=='public' else
            ['authorization_code','client_credentials','urn:ietf:params:oauth:grant-type:token-exchange'])
    provider,created=OAuth2Provider.objects.get_or_create(name=slug,defaults=defaults|{'client_id':slug,'client_secret':secrets.token_urlsafe(48)})
    if not created:
        for k,v in defaults.items(): setattr(provider,k,v)
        provider.save()
    provider.property_mappings.set(list(ScopeMapping.objects.filter(scope_name__in=['openid','profile']))+[scope])
    app,_=Application.objects.update_or_create(slug=slug,defaults=dict(name=slug,provider=provider,policy_engine_mode='all'))
    PolicyBinding.objects.get_or_create(target=app,group=group,order=0,defaults={'enabled':True})
    PolicyBinding.objects.get_or_create(target=app,policy=delegation_policy,order=10,defaults={'enabled':True})
    providers[slug]=provider
# Inventory accepts subjects/actors issued to this API and human CLI tokens.
providers['inventory'].jwt_federation_providers.set(list(providers.values()))
# Permit the confidential API to introspect public CLI tokens; the CLI cannot exchange tokens.
providers['inventory-cli'].jwt_federation_providers.set([providers['inventory']])
print('ELEKTRO_CREDENTIALS='+json.dumps({'client_id':providers['inventory'].client_id,
    'client_secret':providers['inventory'].client_secret,'cli_client_id':providers['inventory-cli'].client_id}))
