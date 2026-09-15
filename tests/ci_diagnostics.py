"""Redact generated CI credentials from container failure diagnostics."""
import json
import sys
from pathlib import Path

values = set()
def collect(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if any(part in key.lower() for part in ('secret', 'password', 'token')) and isinstance(item, str):
                values.add(item)
            collect(item)
    elif isinstance(value, list):
        for item in value:
            collect(item)

for path in Path('.local').glob('ci*'):
    if not path.is_file():
        continue
    for line in path.read_text(errors='replace').splitlines():
        if '=' not in line:
            continue
        key, value = line.split('=', 1)
        if key.startswith('ELEKTRO_'):
            collect(json.loads(value))
        elif any(part in key.lower() for part in ('secret', 'password', 'token')):
            values.add(value)
for line in sys.stdin:
    for value in values:
        if len(value) >= 8:
            line = line.replace(value, '[REDACTED]')
    print(line, end='')
