#!/usr/bin/env python3
"""Validate one site's network settings and render the shared bootstrap inputs."""
import argparse
import ipaddress
import re
import shlex
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]

def validate(site):
    lan = ipaddress.ip_network(site['lan_cidr'])
    pods = ipaddress.ip_network(site['pod_cidr'])
    services = ipaddress.ip_network(site['service_cidr'])
    for net in (lan, pods, services):
        if net.version != 4:
            raise ValueError('This base implements IPv4; IPv6 requires a separate reviewed overlay')
    if lan.overlaps(pods) or lan.overlaps(services) or pods.overlaps(services):
        raise ValueError('LAN, pod and service networks must not overlap')
    addresses = [site[k] for k in ('api_address','dns_address','gateway_address','external_gateway_address')]
    if len(set(addresses)) != len(addresses):
        raise ValueError('API, DNS and both gateway addresses must be distinct')
    for raw in addresses:
        address = ipaddress.ip_address(raw)
        if address not in lan or address in (lan.network_address,lan.broadcast_address):
            raise ValueError(f'{raw} must be a usable address in the LAN subnet')
    if ipaddress.ip_address(site['cluster_dns']) not in services:
        raise ValueError('cluster_dns must be inside service_cidr')
    upstreams = site['dns_upstreams']
    if not upstreams:
        raise ValueError('At least one independent upstream DNS server is required')
    for raw in upstreams:
        address = ipaddress.ip_address(raw)
        if address.is_loopback or raw in addresses[1:] or address in pods or address in services:
            raise ValueError('DNS upstream would create a forwarding loop or use a cluster address')
    for k in ('longhorn_replicas','postgres_instances','platform_replicas'):
        if type(site[k]) is not int or not 1 <= site[k] <= 9:
            raise ValueError(f'{k} must be an integer from 1 to 9')
    if not re.fullmatch(r'[a-z0-9][a-z0-9.-]+[a-z0-9]', site['external_domain']):
        raise ValueError('external_domain must be a DNS name')
    re.compile(site['lan_interface_regex'])
    if '\n' in site['lan_interface_regex'] or '${' in site['lan_interface_regex']:
        raise ValueError('Invalid interface regular expression')
    seen = set()
    for node in site['nodes']:
        if not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]*[a-z0-9])?',node['name']) or node['name'] in seen:
            raise ValueError('Node names must be unique lowercase DNS labels')
        seen.add(node['name'])
        addr = ipaddress.ip_address(node['address'])
        if addr not in lan or node['address'] in addresses[1:]:
            raise ValueError('Node addresses must be in the LAN, outside the service VIPs')
    return site

def render(site):
    validate(site)
    settings_path = ROOT/'clusters/lan/settings.yaml'
    settings = yaml.safe_load(settings_path.read_text())
    mapping = dict(CLUSTER_NAME='cluster_name',GIT_URL='repository',GIT_BRANCH='branch',LAN_CIDR='lan_cidr',
        LAN_INTERFACE_REGEX='lan_interface_regex',API_ADDRESS='api_address',DNS_ADDRESS='dns_address',
        GATEWAY_ADDRESS='gateway_address',EXTERNAL_GATEWAY_ADDRESS='external_gateway_address',
        POD_CIDR='pod_cidr',SERVICE_CIDR='service_cidr',LONGHORN_REPLICAS='longhorn_replicas',
        POSTGRES_INSTANCES='postgres_instances',PLATFORM_REPLICAS='platform_replicas',EXTERNAL_DOMAIN='external_domain')
    data={k:str(site[v]) for k,v in mapping.items()}
    data['DNS_UPSTREAMS']=' '.join(site['dns_upstreams'])
    settings['data']=data
    settings_path.write_text(yaml.safe_dump(settings,sort_keys=False))
    dns_path=ROOT/'infrastructure/dns/config.yaml'
    dns=yaml.safe_load(dns_path.read_text())
    dns['data']['nodes.hosts']='${API_ADDRESS} api.admin.internal\n${DNS_ADDRESS} dns.admin.internal\n'+''.join(
        f"{n['address']} {n['name']}.internal\n" for n in site['nodes'])
    dns_path.write_text(yaml.safe_dump(dns,sort_keys=False))
    local=ROOT/'.local'
    local.mkdir(mode=0o700,exist_ok=True)
    values=(ROOT/'infrastructure/cilium/values.yaml').read_text()
    for key,value in data.items():
        values=values.replace('${'+key+'}',value)
    (local/'cilium-values.yaml').write_text(values)
    env=data|{'CLUSTER_DNS':site['cluster_dns']}
    (local/'site.env').write_text(''.join(f'{key}={shlex.quote(value)}\n' for key,value in env.items()))
    versions=yaml.safe_load((ROOT/'config/versions.yaml').read_text())
    (local/'versions.env').write_text(''.join(f'{key.upper()}_VERSION={shlex.quote(value)}\n' for key,value in versions.items()))
    for file in local.iterdir():
        if file.is_file(): file.chmod(0o600)
    source_path=ROOT/'bootstrap/source.yaml'
    source=yaml.safe_load(source_path.read_text())
    source['spec']['url']=site['repository']
    source['spec']['ref']['branch']=site['branch']
    source_path.write_text(yaml.safe_dump(source,sort_keys=False))

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('site',nargs='?',default=str(ROOT/'config/site.yaml'))
    args=parser.parse_args()
    render(yaml.safe_load(Path(args.site).read_text()))
    print('Site validated. Review and commit clusters/lan/settings.yaml, DNS records, and bootstrap/source.yaml.')
