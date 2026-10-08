"""Atomic status files, immutable checkpoint bundles and exclusive writer locks."""
from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import time
from uuid import uuid4
from ..cars import CARS
from ..tracks import TRACKS
from ..sim import SIM_VERSION, require_version, OBSERVATION_NAMES, ACTION_NAMES
from ..config import ENVIRONMENT


def slug(name: str) -> str:
    return name.lower().replace(' ','_')


def run_path(root: Path, car_id: int, track_id: int) -> Path:
    return root/slug(TRACKS[track_id].spec.name)/slug(CARS[car_id].name)


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):
        return default


def atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    temp = path.with_name(path.name+f'.{uuid4().hex}.tmp')
    with temp.open('w',encoding='utf-8') as stream:
        json.dump(data,stream,indent=2,allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    for attempt in range(10):
        try:
            os.replace(temp,path)
            return
        except PermissionError:
            if attempt==9:
                raise
            time.sleep(.02)


@contextmanager
def writer_lock(run: Path):
    run.mkdir(parents=True,exist_ok=True)
    handle = (run/'writer.lock').open('a+b')
    handle.seek(0,2)
    if handle.tell()==0:
        handle.write(b'0'); handle.flush()
    handle.seek(0)
    locked = False
    try:
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        locked = True
        yield
    finally:
        if locked:
            handle.seek(0)
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else:
                import fcntl
                fcntl.flock(handle,fcntl.LOCK_UN)
        handle.close()


def ensure_freeze(root: Path, experiment: bool = False) -> None:
    if experiment:
        return
    path = root/'physics_lock.json'
    if path.exists():
        lock = read_json(path)
        if not isinstance(lock,dict) or 'sim_version' not in lock:
            raise ValueError(f'Invalid physics lock: {path}')
        require_version(lock['sim_version'])
    else:
        atomic_json(path,{'sim_version':SIM_VERSION,'created_utc':datetime.now(timezone.utc).isoformat()})


def file_hash(path: Path) -> str:
    digest=sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            digest.update(chunk)
    return digest.hexdigest()


def save_checkpoint(model, normalizer, run: Path, metadata: dict) -> Path:
    checkpoints=run/'checkpoints'
    checkpoints.mkdir(parents=True,exist_ok=True)
    token=uuid4().hex[:8]
    temporary=checkpoints/f'.partial-{token}'
    temporary.mkdir()
    model.save(temporary/'model.zip')
    normalizer.save(temporary/'vecnormalize.pkl')
    data=dict(metadata,steps=int(model.num_timesteps),sim_version=SIM_VERSION,
              observation_names=list(OBSERVATION_NAMES),action_names=list(ACTION_NAMES),
              frame_skip=ENVIRONMENT.frame_skip,created_utc=datetime.now(timezone.utc).isoformat(),
              files={name:file_hash(temporary/name) for name in ('model.zip','vecnormalize.pkl')})
    atomic_json(temporary/'metadata.json',data)
    final=checkpoints/f'step_{model.num_timesteps:012d}_{token}'
    os.replace(temporary,final)
    atomic_json(run/'latest.json',{'checkpoint':final.name,'steps':model.num_timesteps})
    return final


def validate_checkpoint(path: Path, car_id=None, track_id=None, *, verify_files: bool = True) -> dict:
    data=read_json(path/'metadata.json')
    if not isinstance(data,dict):
        raise ValueError(f'Missing or corrupt checkpoint metadata: {path}')
    require_version(data.get('sim_version','missing'))
    for key,expected in (('car_id',car_id),('track_id',track_id)):
        if expected is not None and data.get(key)!=expected:
            raise ValueError(f'Checkpoint {key} does not match requested driver')
    if data.get('observation_names')!=list(OBSERVATION_NAMES) or data.get('action_names')!=list(ACTION_NAMES):
        raise ValueError('Checkpoint observation/action contract mismatch')
    if data.get('frame_skip')!=ENVIRONMENT.frame_skip:
        raise ValueError('Checkpoint action frequency mismatch')
    for name in ('model.zip','vecnormalize.pkl'):
        if not (path/name).is_file():
            raise ValueError(f'Checkpoint is missing {name}')
        if verify_files and data.get('files',{}).get(name)!=file_hash(path/name):
            raise ValueError(f'Checkpoint checksum failed: {name}')
    return data


def latest_checkpoint(run: Path, *, car_id=None, track_id=None) -> Path | None:
    pointer=read_json(run/'latest.json',{})
    candidates=sorted((run/'checkpoints').glob('step_*'),reverse=True)
    if pointer.get('checkpoint'):
        name=pointer['checkpoint']
        if Path(name).name!=name:
            raise ValueError('Invalid checkpoint pointer')
        pointed=run/'checkpoints'/name
        candidates=[pointed]+[p for p in candidates if p!=pointed]
    errors=[]
    for path in candidates:
        try:
            validate_checkpoint(path,car_id,track_id)
            return path
        except ValueError as error:
            # A version mismatch requires deliberate retraining, never silently
            # falling back to an unrelated earlier version.
            if 'Simulation mismatch' in str(error):
                raise
            errors.append(str(error))
    if candidates:
        raise ValueError('No complete compatible checkpoint found: '+'; '.join(errors[:3]))
    return None
