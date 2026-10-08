"""Content stamp of the complete simulation contract, independent of client code."""
from hashlib import sha256
from pathlib import Path
import ast


def version_hash() -> str:
    root = Path(__file__).resolve().parents[1]
    names = ['cars.py','tracks.py','rl/env.py','rl/reward.py'] + [f'sim/{name}' for name in (
        'state.py','physics.py','collisions.py','world.py','laps.py','sensors.py')]
    digest = sha256()
    for name in names:
        # AST ignores comments, newlines and formatting, including Windows CRLF.
        tree = ast.parse((root/name).read_text(encoding='utf-8'))
        digest.update(name.encode())
        digest.update(ast.dump(tree,include_attributes=False).encode())
    tree = ast.parse((root/'config.py').read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node,ast.ClassDef) and node.name in ('PhysicsConfig','TrackConfig','SensorConfig','EnvironmentConfig','RewardConfig'):
            digest.update(ast.dump(node,include_attributes=False).encode())
    return digest.hexdigest()


SIM_VERSION = version_hash()


def require_version(saved_version: str) -> None:
    if saved_version != SIM_VERSION:
        raise ValueError(f'Simulation mismatch: model {saved_version}, current {SIM_VERSION}. Retraining required.')
