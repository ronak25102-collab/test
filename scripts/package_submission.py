"""Create a LOCAL draft source archive, including authorized uncommitted changes."""
import hashlib
import json
import re
import subprocess
import zipfile
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    files = subprocess.check_output(['git', 'ls-files', '-co', '--exclude-standard', '-z'], cwd=root).decode().split('\0')
    archive = root / 'output/submission-draft.zip'
    archive.parent.mkdir(exist_ok=True)
    entries = {}
    for name in sorted(set(files) - {''}):
        path = root / name
        if not path.is_file():
            continue
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise RuntimeError('Refusing an external or symlinked source path')
        if name == '.env' or name == 'config/model-rates.json' or any(part in name.split('/') for part in ['.venv', 'node_modules', '.git']):
            raise RuntimeError('Credential/runtime file appeared in source list')
        data = path.read_bytes()
        if re.search(rb'(?:nvapi-[A-Za-z0-9_-]{20,}|tvly-(?:dev|prod)-[A-Za-z0-9_-]{20,})', data):
            raise RuntimeError('Credential-shaped data found; archive was not created')
        entries[name] = data
    manifest = {name: hashlib.sha256(data).hexdigest() for name, data in entries.items()}
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for name, data in entries.items():
            bundle.writestr(name, data)
        bundle.writestr('SOURCE-MANIFEST.json', json.dumps(manifest, indent=2))
    print(json.dumps({'local_draft': str(archive), 'source_files': len(entries),
                      'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
                      'submitted_or_published': False}, indent=2))


if __name__ == '__main__':
    main()
