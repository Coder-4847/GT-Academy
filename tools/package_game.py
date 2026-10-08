"""Build a Windows source distribution with validated AI bundles, never training data."""
import argparse
import json
from pathlib import Path
import zipfile
from gt_academy.rl.tiers import outside_runs,unpack_bundle
from gt_academy.rl.storage import file_hash
from gt_academy.game.racing import OpponentLibrary,TIERS


def package(output):
    output=Path(output)
    outside_runs(output)
    if output.suffix.lower()!='.zip': raise ValueError('Package output must be a .zip file')
    paths=[]
    for directory in ('gt_academy','tools','tests','docs'):
        paths.extend(p for p in Path(directory).rglob('*') if p.is_file() and p.suffix in ('.py','.md') and '__pycache__' not in p.parts)
    paths.extend(Path(p) for p in ('README.md','PHASE_REPORT.md','DECISIONS.md','TRAINING_GUIDE.md','requirements.txt','requirements-lock.txt','pyproject.toml','setup.cmd','launch.cmd','package.cmd'))
    paths.append(Path('assets/ai/manifest.json'))
    library=OpponentLibrary()
    for t in range(5):
        for c in range(5):
            for tier in TIERS:
                row,bundle=library.stats(c,t,tier)
                if file_hash(bundle)!=row['sha256']: raise ValueError(f'Corrupt bundle: {bundle}')
                unpack_bundle(bundle,Path('artifacts/package-validation'),c,t)
                paths.extend((bundle.relative_to(Path.cwd()),bundle.with_suffix('.json').relative_to(Path.cwd())))
    if output.resolve() in {p.resolve() for p in paths}: raise ValueError('Output cannot overwrite a packaged input')
    output.parent.mkdir(parents=True,exist_ok=True)
    temporary=output.with_suffix('.tmp')
    manifest={p.as_posix():file_hash(p) for p in sorted(set(paths))}
    with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as archive:
        for name in manifest: archive.write(name,'GT Academy/'+name)
        archive.writestr('GT Academy/PACKAGE-CHECKSUMS.json',json.dumps(manifest,indent=2))
    with zipfile.ZipFile(temporary) as archive:
        if archive.testzip() is not None: raise ValueError('Package integrity check failed')
    temporary.replace(output)
    print(f'Created {output} ({output.stat().st_size/1024**2:.1f} MiB), {len(manifest)} verified files. No runs or player data included.')
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('artifacts/GT-Academy-Windows.zip'))
    args=parser.parse_args()
    package(args.output)


if __name__=='__main__': main()
