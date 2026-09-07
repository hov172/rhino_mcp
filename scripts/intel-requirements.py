"""Add the verified locally built Intel wheel hash to locked requirements."""
from pathlib import Path
import hashlib
import json
import sys

requirements, wheelhouse, output = map(Path, sys.argv[1:])
record = json.loads((wheelhouse/'cryptography-intel-provenance.json').read_text())
wheel = wheelhouse/record['wheel']
assert hashlib.sha256(wheel.read_bytes()).hexdigest() == record['wheel_sha256']
needle = f"cryptography=={record['version']} \\\n"
text = requirements.read_text()
assert needle in text, 'Locked cryptography version differs from Intel build'
text = text.replace(needle, needle + f"    --hash=sha256:{record['wheel_sha256']} \\\n", 1)
output.write_text(text)
