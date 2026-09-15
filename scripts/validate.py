#!/usr/bin/env python3
"""Offline invariants for the bootstrap, Flux graph, secrets and exposure boundaries."""
import json,re,sys
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from configure import validate

class UniqueLoader(yaml.SafeLoader): pass
def unique_mapping(loader,node,deep=False):
    result={}
    for key_node,value_node in node.value:
        key=loader.construct_object(key_node,deep=deep)
        if key in result: raise ValueError(f'Duplicate YAML key: {key}')
        result[key]=loader.construct_object(value_node,deep=deep)
    return result
UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,unique_mapping)
def docs(path): return list(yaml.load_all(path.read_text(),Loader=UniqueLoader))

def main():
    validate(yaml.safe_load((ROOT/'config/site.example.yaml').read_text()))
    parsed={}
    for path in ROOT.rglob('*.yaml'):
        if any(x in path.parts for x in ('.git','.local','.venv')) or path.name=='site.yaml': continue
        # Authentik blueprint tags are parsed by authentik; here check their YAML structure.
        if path.parent.name=='identity-config' and path.name=='platform.yaml':
            class BlueprintLoader(UniqueLoader): pass
            BlueprintLoader.add_multi_constructor('!',lambda l,t,n:l.construct_sequence(n) if isinstance(n,yaml.SequenceNode) else l.construct_scalar(n))
            yaml.load(path.read_text(),Loader=BlueprintLoader);continue
        parsed[path]=docs(path)
    settings=yaml.safe_load((ROOT/'clusters/lan/settings.yaml').read_text())['data']
    for path,items in parsed.items():
        if '.github' in path.parts: continue
        for variable in re.findall(r'\$\{([A-Z][A-Z0-9_]*)\}',path.read_text()):
            assert variable in settings, f'{path}: missing Flux substitution {variable}'
        for d in items:
            if not isinstance(d,dict): continue
            if d.get('kind')=='Secret' and 'sops' not in d:
                raise AssertionError(f'{path}: plaintext Kubernetes Secret must not be tracked')
            if d.get('kind')=='Kustomization' and d.get('apiVersion','').startswith('kustomize.config'):
                for ref in d.get('resources',[]):
                    assert ref.startswith('https://') or (path.parent/ref).exists(),f'{path}: missing resource {ref}'
            if d.get('kind')=='HelmRelease':
                assert re.fullmatch(r'v?\d+\.\d+\.\d+',d['spec']['chart']['spec']['version']),f'{path}: chart must be pinned'
    stages={d['metadata']['name']:d for d in parsed[ROOT/'clusters/lan/reconciliation.yaml']}
    visiting=set();visited=set()
    def walk(name):
        assert name in stages,f'Unknown dependency {name}'
        assert name not in visiting,'Flux dependency cycle'
        if name in visited:return
        visiting.add(name)
        for dep in stages[name]['spec'].get('dependsOn',[]): walk(dep['name'])
        visiting.remove(name);visited.add(name)
        assert (ROOT/stages[name]['spec']['path']/'kustomization.yaml').exists(),f'Missing stage directory {name}'
    for name in stages:walk(name)
    for name in ('cilium','gateway-api','longhorn','databases'):
        assert stages[name]['spec']['prune'] is False, f'{name}: destructive pruning must stay disabled'
    cilium=yaml.safe_load((ROOT/'infrastructure/cilium/values.yaml').read_text())
    assert cilium['kubeProxyReplacement'] and cilium['gatewayAPI']['enabled'] and cilium['l2announcements']['enabled']
    dns=parsed[ROOT/'infrastructure/dns/server.yaml'][1]
    assert dns['spec']['externalTrafficPolicy']=='Cluster'
    assert {p['protocol'] for p in dns['spec']['ports']}=={'TCP','UDP'}
    gateway=parsed[ROOT/'infrastructure/gateways/internal.yaml'][1]
    assert gateway['spec']['infrastructure']['annotations']['io.cilium/lb-ipam-ips']=='${GATEWAY_ADDRESS}'
    routes=parsed[ROOT/'platform/authentik/routes.yaml']
    assert all(r['spec']['rules'][0]['backendRefs'][0]['name']=='authentik-server' for r in routes)
    assert not any('examples/external-gateway' in s['spec']['path'] for s in stages.values()),'External gateway must be opt-in'
    model=json.loads((ROOT/'platform/openfga/model.json').read_text())
    assert {t['type'] for t in model['type_definitions']}=={'principal','service','delegation'}
    for path in ROOT.rglob('*'):
        if path.is_file() and not any(p in path.parts for p in ('.git','.local','__pycache__','.venv')):
            text=path.read_text()
            assert 'BEGIN '+'PRIVATE KEY' not in text and 'AGE-SECRET-'+'KEY-' not in text,f'Private key found: {path}'
    print(f'Validated {len(parsed)} YAML files, {len(stages)} Flux stages, and exposure/secret invariants.')

if __name__=='__main__':main()
