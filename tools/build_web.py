"""Export the unchanged Python simulation and frozen trained actors for static hosting."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import zipfile
import numpy as np
from gt_academy.cars import CARS
from gt_academy.tracks import TRACKS
from gt_academy.sim import SIM_VERSION
from gt_academy.game.racing import OpponentLibrary,TIERS


def main():
    out=Path('web'); (out/'models').mkdir(parents=True,exist_ok=True)
    paths=[Path('gt_academy/__init__.py'),Path('gt_academy/config.py'),Path('gt_academy/cars.py'),Path('gt_academy/tracks.py')]
    paths+=list(Path('gt_academy/sim').glob('*.py'))
    paths+=[Path('gt_academy')/name for name in ('rl/__init__.py','rl/env.py','rl/reward.py','game/__init__.py','game/config.py','game/session.py','game/save.py','game/racing.py')]
    with zipfile.ZipFile(out/'simulation.zip','w',zipfile.ZIP_DEFLATED) as z:
        for path in paths: z.write(path,path.as_posix())
    catalog=dict(sim_version=SIM_VERSION,cars=[asdict(c) for c in CARS],tracks=[],models={})
    for track in TRACKS:
        catalog['tracks'].append(dict(name=track.spec.name,length=track.length,width=track.spec.width,color=track.spec.color,
            center=track.center[::2].tolist()))
    library=OpponentLibrary(); errors=[]
    from web.bridge import NumpyDriver
    rng=np.random.default_rng(492)
    for t in range(5):
        for c in range(5):
            for tier in TIERS:
                driver=library.load(c,t,tier)
                try:
                    weights=driver.model.policy.state_dict()
                    arrays={}
                    for index,prefix in enumerate(('mlp_extractor.policy_net.0','mlp_extractor.policy_net.2','action_net')):
                        for key in ('weight','bias'): arrays[f'{key}{index}']=weights[prefix+'.'+key].detach().cpu().numpy()
                    arrays.update(mean=driver.normalizer.obs_rms.mean,var=driver.normalizer.obs_rms.var,
                        clip=np.array(driver.normalizer.clip_obs),epsilon=np.array(driver.normalizer.epsilon),
                        sim_version=np.array(SIM_VERSION),car=np.array(c),track=np.array(t))
                    name=f'{t}-{c}-{tier.lower()}.npz'; path=out/'models'/name
                    np.savez_compressed(path,**arrays)
                    exported=NumpyDriver(path,c,t)
                    for _ in range(24):
                        raw=rng.uniform(-1,1,32).astype(np.float32)
                        error=float(np.max(np.abs(driver.action(raw)-exported.action(raw))))
                        if error>1e-5: raise ValueError(f'Actor mismatch {name}: {error}')
                        errors.append(error)
                    stats,_=library.stats(c,t,tier)
                    catalog['models'][f'{t}:{c}:{tier}']=dict(file='models/'+name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),mean_lap=stats['mean_lap'])
                finally: driver.close()
            print(f'Exported {TRACKS[t].spec.name} / {CARS[c].name}',flush=True)
    catalog['simulation_sha256']=hashlib.sha256((out/'simulation.zip').read_bytes()).hexdigest()
    (out/'catalog.json').write_text(json.dumps(catalog,separators=(',',':')),encoding='utf-8')
    Path('artifacts/web/export-validation.json').write_text(json.dumps(dict(models=100,observations=len(errors),max_action_error=max(errors),sim_version=SIM_VERSION),indent=2),encoding='utf-8')
    print(f'100 actors exported; max action error {max(errors):.3g}. Frozen source archived unchanged.')


if __name__=='__main__': main()
