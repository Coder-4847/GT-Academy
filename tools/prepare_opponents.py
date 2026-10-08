"""Select tiers that also survive five continuous laps; read-only training access."""
import argparse,json
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
from gt_academy.rl.runtime import configure_environment
configure_environment()


def prepare_pair(car,track,rows,laps,cache):
    from gt_academy.rl.runtime import configure_torch
    from gt_academy.rl.tiers import choose_tiers
    from gt_academy.rl.policy import Driver
    from gt_academy.game.racing import Opponent
    configure_torch()
    candidates=[r for r in rows if r['car_id']==car and r['track_id']==track]
    checks=dict(cache)
    while True:
        eligible=[r for r in candidates if r['checkpoint'] not in checks or checks[r['checkpoint']]['completed_laps']>=laps]
        selected,_=choose_tiers(eligible)
        pending={r['checkpoint']:r for r in selected.values() if r['checkpoint'] not in checks}
        if not pending:
            return [dict(r,race_validation=checks[r['checkpoint']]) for r in eligible if r['checkpoint'] in checks],checks
        for path,row in pending.items():
            driver=Driver(Path(path),car,track)
            opponent=Opponent(driver,car,track,laps)
            try:
                while opponent.finish_time is None and not opponent.dnf: opponent.step()
                checks[path]={'completed_laps':len(opponent.sim.lap.lap_times),'requested_laps':laps,
                              'lap_times':opponent.sim.lap.lap_times,'finish_time':opponent.finish_time,'dnf':opponent.dnf}
            finally: driver.close()


def main():
    from gt_academy.sim import SIM_VERSION
    from gt_academy.rl.tiers import build,outside_runs
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results',type=Path,default=Path('artifacts/checkpoint-evaluations.json'))
    parser.add_argument('--root',type=Path,default=Path('runs'))
    parser.add_argument('--output',type=Path,default=Path('assets/ai'))
    parser.add_argument('--workers',type=int,default=4)
    parser.add_argument('--laps',type=int,default=5)
    parser.add_argument('--cache',type=Path,default=Path('artifacts/phase4/continuous-race-checks.json'))
    args=parser.parse_args()
    if args.workers<1 or args.laps<3: parser.error('Use positive workers and at least three continuous laps')
    outside_runs(args.cache,args.root); outside_runs(args.output,args.root)
    rows=json.loads(args.results.read_text(encoding='utf-8'))['results']
    cached={}
    if args.cache.exists():
        data=json.loads(args.cache.read_text(encoding='utf-8'))
        if data.get('sim_version')==SIM_VERSION and data.get('laps')==args.laps: cached=data.get('checks',{})
    prepared=[]; errors=[]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(prepare_pair,c,t,rows,args.laps,{k:v for k,v in cached.items() if any(r['checkpoint']==k and r['car_id']==c and r['track_id']==t for r in rows)}):(c,t) for t in range(5) for c in range(5)}
        for future in as_completed(futures):
            c,t=futures[future]
            try:
                chosen,checks=future.result(); prepared.extend(chosen); cached.update(checks)
                print(f'{t}:{c}: continuous-race selection ready ({len(checks)} checkpoints checked)',flush=True)
            except Exception as error:
                errors.append(f'{t}:{c}: {error}'); print(errors[-1],flush=True)
            args.cache.parent.mkdir(parents=True,exist_ok=True)
            temp=args.cache.with_suffix('.tmp')
            temp.write_text(json.dumps({'sim_version':SIM_VERSION,'laps':args.laps,'checks':cached},indent=2),encoding='utf-8'); temp.replace(args.cache)
    if errors: raise SystemExit('No export made: '+'; '.join(errors))
    vetted=args.cache.with_name('race-vetted-evaluations.json')
    vetted.write_text(json.dumps({'sim_version':SIM_VERSION,'results':prepared},indent=2),encoding='utf-8')
    manifest=build(args.root,args.output,prepared)
    print(f'Exported 100 tiers, each completing {args.laps} continuous laps. {len(manifest["warnings"])} pace-spacing warnings.',flush=True)


if __name__=='__main__': main()
