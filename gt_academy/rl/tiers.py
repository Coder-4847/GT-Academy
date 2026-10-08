"""Read-only checkpoint selection and self-contained exported opponent bundles."""
import json
import math
from pathlib import Path
import zipfile
from ..sim import SIM_VERSION,require_version
from ..cars import CARS
from ..tracks import TRACKS
from .storage import validate_checkpoint,read_json,slug,file_hash

TIERS=('Rookie','Pro','Champion','Legend')
TARGETS=(1.375,1.12,1.03,1.)


def outside_runs(output,root=Path('runs')):
    if Path(output).resolve().is_relative_to(Path(root).resolve()):
        raise ValueError('Outputs must be outside the protected training folder.')


def collect_evaluations(root):
    rows=[]
    for checkpoint in sorted(Path(root).glob('*/*/checkpoints/step_*')):
        result=read_json(checkpoint/'evaluation.json',{})
        if not result: continue
        metadata=validate_checkpoint(checkpoint)
        rows.append(dict(result,checkpoint=str(checkpoint.resolve()),car_id=metadata['car_id'],
                         track_id=metadata['track_id'],sim_version=metadata['sim_version'],source='training evaluation'))
    return rows


def choose_tiers(rows):
    reliable=[r for r in rows if r.get('episodes',0)>=3 and r.get('completion_rate',0)>=1.
              and isinstance(r.get('mean_lap'),(int,float)) and math.isfinite(r['mean_lap']) and r['mean_lap']>0]
    if not reliable: raise ValueError('No checkpoint has three fully completed evaluation laps.')
    reliable.sort(key=lambda r:(r['mean_lap'],r['checkpoint']))
    best=reliable[0]['mean_lap']
    selection={}
    previous=float('inf')
    warnings=[]
    for tier,target in zip(TIERS,TARGETS):
        candidates=[r for r in reliable if r['mean_lap']<=previous]
        band=[r for r in candidates if 1.3<=r['mean_lap']/best<=1.45]
        if tier=='Rookie' and band: chosen=max(band,key=lambda r:r['mean_lap'])
        else: chosen=min(candidates,key=lambda r:abs(r['mean_lap']/best-target))
        selection[tier]=chosen
        ratio=chosen['mean_lap']/best
        if abs(ratio-target)>.06: warnings.append(f'{tier}: available pace {ratio:.1%}, target {target:.1%}')
        if previous<float('inf') and previous/chosen['mean_lap']<1.015:
            warnings.append(f'{tier}: less than 1.5% faster than preceding tier')
        previous=chosen['mean_lap']
    return selection,warnings


def build(root,output,rows):
    outside_runs(output,root)
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    manifest={'sim_version':SIM_VERSION,'pairs':{},'warnings':[]}
    for track in range(5):
        for car in range(5):
            candidates=[r for r in rows if r.get('car_id')==car and r.get('track_id')==track]
            selected,warnings=choose_tiers(candidates)
            key=f'{track}:{car}'
            manifest['pairs'][key]={}
            for tier,row in selected.items():
                require_version(row['sim_version'])
                checkpoint=Path(row['checkpoint'])
                metadata=validate_checkpoint(checkpoint,car,track)
                relative=Path(slug(TRACKS[track].spec.name))/slug(CARS[car].name)/(tier.lower()+'.zip')
                destination=output/relative; destination.parent.mkdir(parents=True,exist_ok=True)
                stats=dict(row,tier=tier,source_checkpoint=checkpoint.name,steps=metadata['steps'])
                temporary=destination.with_suffix('.tmp')
                with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_STORED) as archive:
                    for name in ('model.zip','vecnormalize.pkl','metadata.json'): archive.write(checkpoint/name,name)
                    archive.writestr('stats.json',json.dumps(stats,indent=2))
                temporary.replace(destination)
                destination.with_suffix('.json').write_text(json.dumps(stats,indent=2),encoding='utf-8')
                manifest['pairs'][key][tier]=dict(stats,bundle=relative.as_posix(),sha256=file_hash(destination))
            manifest['warnings'].extend(f'{TRACKS[track].spec.name}/{CARS[car].name}: {w}' for w in warnings)
    temporary=output/'manifest.tmp'
    temporary.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    temporary.replace(output/'manifest.json')
    return manifest


def unpack_bundle(bundle,cache,car,track):
    """Extract only known files from our local export; always validate identities."""
    outside_runs(cache)
    bundle=Path(bundle)
    destination=Path(cache)/file_hash(bundle)
    destination.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(bundle) as archive:
        names=('model.zip','vecnormalize.pkl','metadata.json','stats.json')
        if set(archive.namelist())!=set(names): raise ValueError('Invalid AI bundle contents')
        metadata=json.loads(archive.read('metadata.json'))
        require_version(metadata.get('sim_version','missing'))
        for name in names:
            if not (destination/name).exists():
                (destination/name).write_bytes(archive.read(name))
    validate_checkpoint(destination,car,track)
    return destination
