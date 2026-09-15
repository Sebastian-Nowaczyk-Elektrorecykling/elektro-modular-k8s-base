#!/usr/bin/env python3
"""Manage explicit service grants and agent identities using administrator Kubernetes access."""
import argparse
import json
import os
import re
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
sub=parser.add_subparsers(dest='command',required=True)
sub.add_parser('users')
for cmd in ('grant','revoke'):
    p=sub.add_parser(cmd);p.add_argument('username');p.add_argument('service',choices=['longhorn','hubble','inventory'])
p=sub.add_parser('actor');p.add_argument('name');p.add_argument('--parent');p.add_argument('--days',type=int,default=30)
args=parser.parse_args()
if args.command=='actor' and (not re.fullmatch('[a-z][a-z0-9-]{0,60}',args.name) or not 1<=args.days<=90):
    parser.error('Actor name must be a DNS label and lifetime 1–90 days')

code='REQUEST='+repr(vars(args))+'''
import json,secrets
from datetime import timedelta
from django.utils import timezone
from authentik.core.models import Actor,Group,User,Token,TokenIntents,UserTypes
cmd=REQUEST['command']
result={}
if cmd=='users':
    result={'users':list(User.objects.values('username','uuid','is_active','type'))}
elif cmd in ('grant','revoke'):
    user=User.objects.get(username=REQUEST['username'])
    group=Group.objects.get(name='service-'+REQUEST['service'])
    if cmd=='grant': user.groups.add(group)
    else: user.groups.remove(group)
    result={'username':user.username,'uuid':str(user.uuid),'service':REQUEST['service'],'action':cmd}
elif cmd=='actor':
    if User.objects.filter(username=REQUEST['name']).exists(): raise ValueError('Identity already exists; no token rotation is implicit')
    parent=User.objects.get(username=REQUEST['parent']) if REQUEST['parent'] else None
    expires=timezone.now()+timedelta(days=REQUEST['days'])
    if parent:
        actor=Actor.objects.create(username=REQUEST['name'],name=REQUEST['name'],parent=parent,
            policy_behavior='none',type=UserTypes.SERVICE_ACCOUNT,is_active=True,
            expiring=True,expires=expires)
    else:
        # 2026.8.2's audit serializer dereferences Actor.parent unconditionally.
        # An autonomous identity uses the supported ordinary service-account model.
        actor=User.objects.create(username=REQUEST['name'],name=REQUEST['name'],
            type=UserTypes.SERVICE_ACCOUNT,is_active=True)
    actor.set_unusable_password();actor.save()
    token=Token.objects.create(identifier='elektro-'+REQUEST['name'],user=actor,key=secrets.token_urlsafe(48),
        intent=TokenIntents.INTENT_APP_PASSWORD,expiring=True,expires=expires)
    result={'username':actor.username,'uuid':str(actor.uuid),'parent':str(parent.uuid) if parent else None,
            'app_password':token.key,'expires':str(expires)}
print('ELEKTRO_RESULT='+json.dumps(result,default=str))
'''
out=subprocess.run(['kubectl','-n','identity','exec','-i','deployment/authentik-worker','--','ak','shell','-c',
    'exec(__import__("sys").stdin.read())'],input=code,text=True,capture_output=True,check=True)
result=json.loads(next(x.split('=',1)[1] for x in out.stdout.splitlines() if x.startswith('ELEKTRO_RESULT=')))
if args.command=='actor':
    os.umask(0o077)
    path=ROOT/'.local'/('actor-'+args.name+'.json');path.parent.mkdir(mode=0o700,exist_ok=True)
    path.write_text(json.dumps(result,indent=2)+'\n')
    print(f'Created actor {result["uuid"]}; credentials saved to {path.relative_to(ROOT)}')
else: print(json.dumps(result,indent=2))
