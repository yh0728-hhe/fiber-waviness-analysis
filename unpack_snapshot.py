#!/usr/bin/env python3
"""Restore the two large, losslessly compressed snapshot files using stdlib."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results-dir', type=Path, default=Path(__file__).resolve().parent/'results')
    args = parser.parse_args()
    base = args.results_dir.resolve()
    manifest = json.loads((base/'compressed_snapshot_manifest.json').read_text())
    for item in manifest['files']:
        target = base/item['uncompressed_name']
        source = base/item['compressed_name']
        if target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest() != item['uncompressed_sha256']:
                raise SystemExit(f'Refusing to overwrite a different existing file: {target.name}')
            print(f'Already verified: {target.name}')
            continue
        with gzip.open(source,'rb') as f:
            data = f.read()
        if len(data) != item['uncompressed_bytes'] or hashlib.sha256(data).hexdigest() != item['uncompressed_sha256']:
            raise SystemExit(f'Integrity check failed: {source.name}')
        target.write_bytes(data)
        print(f'Restored and verified: {target.name} ({len(data):,} bytes)')


if __name__ == '__main__':
    main()
