#!/usr/bin/env python3
import argparse,ssl
from pathlib import Path
from urllib.request import Request,urlopen
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description='Call the inventory example without placing a bearer token in process arguments.')
p.add_argument('token_file');p.add_argument('--ca',default=str(ROOT/'.local/internal-ca.crt'));args=p.parse_args()
req=Request('https://inventory.internal/',headers={'Authorization':'Bearer '+Path(args.token_file).read_text().strip()})
with urlopen(req,context=ssl.create_default_context(cafile=args.ca),timeout=15) as r:print(r.read().decode())
