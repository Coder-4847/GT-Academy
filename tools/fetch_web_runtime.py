"""Vendor the pinned Python 3.12 browser runtime so Pages needs no runtime CDN."""
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen


def main():
    root=Path('web/vendor/pyodide'); root.mkdir(parents=True,exist_ok=True)
    base='https://cdn.jsdelivr.net/pyodide/v0.27.7/full/'
    def fetch(name,expected=None):
        path=root/name
        if not path.exists():
            with urlopen(base+name,timeout=90) as response: path.write_bytes(response.read())
        if expected and hashlib.sha256(path.read_bytes()).hexdigest()!=expected: raise ValueError(f'Checksum mismatch: {name}')
        print(f'{name}: {path.stat().st_size:,} bytes',flush=True)
    for name in ('pyodide.mjs','pyodide.asm.js','pyodide.asm.wasm','python_stdlib.zip','pyodide-lock.json'): fetch(name)
    lock=json.loads((root/'pyodide-lock.json').read_text())
    done=set()
    def package(name):
        if name in done:return
        done.add(name); data=lock['packages'][name]
        for dependency in data['depends']: package(dependency)
        fetch(data['file_name'],data['sha256'])
    package('numpy')
    fetch('pyodide.js')
    # Upstream distribution license, shipped alongside the runtime.
    with urlopen('https://raw.githubusercontent.com/pyodide/pyodide/0.27.7/LICENSE',timeout=30) as r:
        (root/'LICENSE').write_bytes(r.read())


if __name__=='__main__':main()
