"""Executed only inside the ephemeral CI authentik worker."""
import json,secrets
from datetime import timedelta
from django.utils import timezone
from authentik.core.models import Actor,User,Group,Token,TokenIntents,UserTypes,Application
from authentik.policies.models import PolicyBinding

user=User.objects.create(username='ci-user',name='CI user',is_active=True)
actors=[Actor.objects.create(username=name,name=name,parent=parent,policy_behavior='none',
    type=UserTypes.SERVICE_ACCOUNT,is_active=True,expiring=True,expires=timezone.now()+timedelta(hours=1))
    for name,parent in [('ci-agent',user),('ci-independent',None)]]
child=Actor.objects.create(username='ci-child',name='CI child',parent=actors[0],policy_behavior='none',
    type=UserTypes.SERVICE_ACCOUNT,is_active=True,expiring=True,expires=timezone.now()+timedelta(hours=1))
result={}
for u in [user,*actors,child]:
    u.groups.add(Group.objects.get(name='service-inventory'))
    tok=Token.objects.create(identifier='test-'+u.username,user=u,intent=TokenIntents.INTENT_APP_PASSWORD,
        key=secrets.token_urlsafe(40),expiring=True,expires=timezone.now()+timedelta(hours=1))
    result[u.username]={'username':u.username,'uuid':str(u.uuid),'app_password':tok.key}
for slug in ('longhorn','hubble'):
    app=Application.objects.get(slug=slug)
    assert PolicyBinding.objects.filter(target=app,group__name='service-'+slug).exists()
print('ELEKTRO_FIXTURE='+json.dumps(result))
