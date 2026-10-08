"""Read-only live status for all 25 car/track pairs."""
import argparse
import os
from pathlib import Path
import sys
import time
if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gt_academy.config import TRAINING as T
from gt_academy.cars import CARS
from gt_academy.tracks import TRACKS
from gt_academy.rl.storage import read_json,run_path


def snapshot(root: Path, threshold: int) -> str:
    launch=read_json(root/'launcher.json',{})
    jobs={(j['car_id'],j['track_id']):j for j in launch.get('jobs',[])}
    rows=['GT ACADEMY - training status',f'Root: {root.resolve()}',
          f'{"TRACK / CAR":32} {"STEPS":>10} {"STEP/S":>8} {"BEST":>9} {"FINISH":>8}  STATUS']
    for track,t in enumerate(TRACKS):
        for car,c in enumerate(CARS):
            data=read_json(run_path(root,car,track)/'status.json',{})
            job=jobs.get((car,track),{})
            state=data.get('status','waiting')
            if job.get('status') in ('queued','not_started','failed'): state=job['status']
            elif job.get('status')=='running' and data.get('worker_token')!=job.get('worker_token'): state='starting'
            if state in ('training','evaluating') and time.time()-data.get('updated_at',0)>max(120,T.status_seconds*5):
                state+=' (stale heartbeat)'
            if data.get('steps',0)>=threshold and not data.get('training_laps',0): state+=' ! NO FULL LAP'
            best=f'{data["best_lap"]:.2f}s' if data.get('best_lap') is not None else '-'
            evaluation=data.get('evaluation',{})
            finish=f'{evaluation["completion_rate"]:.0%}' if evaluation.get('episodes') else '-'
            rows.append(f'{t.spec.name+" / "+c.name:32} {data.get("steps",0):10,} {data.get("steps_per_second",0):8.0f} {best:>9} {finish:>8}  {state}')
    rows.append('FINISH is deterministic grid-start evaluation; NO FULL LAP refers to training episodes. Ctrl+C closes this monitor only.')
    return '\n'.join(rows)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('runs'))
    p.add_argument('--once',action='store_true')
    p.add_argument('--interval',type=float,default=T.monitor_seconds)
    p.add_argument('--no-lap-steps',type=int,default=T.stalled_lap_steps)
    args=p.parse_args()
    if args.interval<=0 or args.no_lap_steps<=0: p.error('Interval and threshold must be positive')
    try:
        while True:
            if not args.once and sys.stdout.isatty():
                print('\033[2J\033[H',end='')
            print(snapshot(args.root,args.no_lap_steps),flush=True)
            if args.once: break
            time.sleep(args.interval)
    except KeyboardInterrupt: pass


if __name__=='__main__': main()
