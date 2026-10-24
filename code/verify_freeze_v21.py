"""Verify the additive v21 freeze, without modifying the historical freeze."""
from pathlib import Path
import json,hashlib
root=Path(__file__).resolve().parent.parent
checksums=json.loads((root/'SHA256SUMS.json').read_text(encoding='utf-8'))
failures=[]
for name,expected in checksums.items():
    path=root/name
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
        failures.append(name)
if failures:raise SystemExit('Mismatch: '+', '.join(failures))
print(f'v21 freeze verified: {len(checksums)} files')
