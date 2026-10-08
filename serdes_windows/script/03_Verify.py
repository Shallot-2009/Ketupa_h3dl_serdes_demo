"""Verify distributed core hashes without starting EDA software."""
from pathlib import Path
import hashlib
import sys

def main():
    root=Path(__file__).resolve().parents[1]
    manifest=root/'resource/CORE_SHA256SUMS'
    if not manifest.is_file():
        print('FAIL: distribution manifest is missing'); return 1
    failed=[]; checked=0
    for line in manifest.read_text(encoding='utf-8').splitlines():
        digest,relative=line.split('  ',1)
        path=(root/relative).resolve()
        if not path.is_relative_to(root) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            failed.append(relative)
        checked+=1
    for relative in failed: print('FAIL '+relative)
    print(f'Checked {checked} core files; failures={len(failed)}. Hashes are not publisher signatures.')
    return int(bool(failed))

if __name__=='__main__': raise SystemExit(main())
