#!/usr/bin/env python3
"""Render every Kustomize stage and all pinned Helm charts, using the same settings as Flux."""
import re,subprocess
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1]
output=ROOT/'.local/rendered';output.mkdir(parents=True,exist_ok=True)
settings=yaml.safe_load((ROOT/'clusters/lan/settings.yaml').read_text())['data']
def substitute(s):
    return re.sub(r'\$\{([A-Z][A-Z0-9_]*)\}',lambda m:settings[m[1]],s)
repos=list(yaml.safe_load_all((ROOT/'infrastructure/sources/repositories.yaml').read_text()))
for repo in repos:
    subprocess.run(['helm','repo','add',repo['metadata']['name'],repo['spec']['url'],'--force-update'],check=True)
subprocess.run(['helm','repo','update'],check=True)
for file in sorted(ROOT.rglob('kustomization.yaml')):
    if any(p in file.parts for p in ('.local','.git','secrets')): continue
    path=file.parent
    rendered=substitute(subprocess.check_output(['kustomize','build',str(path)],text=True))
    (output/(str(path.relative_to(ROOT)).replace('/','-')+'.yaml')).write_text(rendered)
    documents=list(yaml.safe_load_all(rendered))
    for d in documents:
        if not d or d.get('kind')!='HelmRelease':continue
        spec=d['spec'];chart=spec['chart']['spec'];name=d['metadata']['name'];values=spec.get('values',{})
        if name=='cilium':values=yaml.safe_load(substitute((ROOT/'infrastructure/cilium/values.yaml').read_text()))
        vf=output/(name+'-values.yaml');vf.write_text(yaml.safe_dump(values))
        result=subprocess.check_output(['helm','template',spec['releaseName'],chart['sourceRef']['name']+'/'+chart['chart'],
            '--version',chart['version'],'--namespace',spec['targetNamespace'],'--kube-version','1.36.4',
            '--include-crds','-f',str(vf)],text=True)
        list(yaml.safe_load_all(result))
        (output/(name+'-helm.yaml')).write_text(result)
print('All Kustomize stages and pinned Helm charts rendered successfully.')
