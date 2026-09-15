import copy,sys,unittest
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from configure import validate

class SiteValidation(unittest.TestCase):
    def setUp(self):self.site=yaml.safe_load((ROOT/'config/site.example.yaml').read_text())
    def test_valid_example(self):validate(self.site)
    def test_rejects_overlapping_pod_network(self):
        self.site['pod_cidr']=self.site['lan_cidr']
        with self.assertRaises(ValueError):validate(self.site)
    def test_rejects_out_of_lan_vip(self):
        self.site['gateway_address']='192.168.200.241'
        with self.assertRaises(ValueError):validate(self.site)
    def test_rejects_dns_forwarding_loop(self):
        self.site['dns_upstreams']=[self.site['dns_address']]
        with self.assertRaises(ValueError):validate(self.site)
    def test_rejects_duplicate_vips(self):
        self.site['gateway_address']=self.site['dns_address']
        with self.assertRaises(ValueError):validate(self.site)
    def test_rejects_node_on_service_vip(self):
        self.site['nodes'][0]['address']=self.site['gateway_address']
        with self.assertRaises(ValueError):validate(self.site)
    def test_single_node_profile(self):
        self.site.update(longhorn_replicas=1,postgres_instances=1,platform_replicas=1);validate(self.site)
