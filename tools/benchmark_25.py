"""User-run concurrent PPO throughput benchmark; default is 25 runs for ten minutes."""
import argparse
from datetime import datetime,timezone
from pathlib import Path
import os
import statistics
import sys
if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gt_academy.rl.runtime import configure_environment
configure_environment()
from gt_academy.config import TRAINING as T
from gt_academy.cars import CARS
from gt_academy.tracks import TRACKS
from gt_academy.rl.launcher import parser as launch_parser,launch
from gt_academy.rl.storage import run_path,read_json,atomic_json


def recommendation(rates: list[float], concurrent: int, n_envs: int, cores: int) -> str:
    median=statistics.median(rates) if rates else 0.
    if median>=T.target_env_steps_per_second:
        return f'Keep --max-concurrent {concurrent} --n-envs {n_envs} if temperatures remain comfortable and the sanity test passed.'
    wave=min(12,max(1,cores//2),max(1,concurrent-1))
    return (f'The {T.target_env_steps_per_second:g} environment-step/s target was not reached. '
            f'Re-run with --max-concurrent {wave} --n-envs {n_envs}; this tests waves, not a guaranteed speedup. '
            'If per-run speed stays low, paste the summary for simulation profiling before an overnight run. '
            'You can compare --n-envs 8 separately; larger batches may help inference but add simulation work.')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--minutes',type=float,default=10.)
    p.add_argument('--max-concurrent',type=int,default=25)
    p.add_argument('--n-envs',type=int,default=T.n_envs)
    p.add_argument('--root',type=Path)
    args=p.parse_args()
    if min(args.minutes,args.max_concurrent,args.n_envs)<=0: p.error('All numeric options must be positive')
    root=args.root or Path('experiments')/('benchmark_'+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_utc'))
    if any(root.glob('*/*/checkpoints')): p.error('Use a new root so the benchmark measures a fresh interval')
    options=launch_parser().parse_args(['--root',str(root),'--hours',str(args.minutes/60),
        '--max-concurrent',str(args.max_concurrent),'--n-envs',str(args.n_envs),
        '--evaluate-every','0','--eval-episodes','0','--experiment'])
    print('This runs real short PPO updates. Monitor laptop temperatures in your vendor utility; Windows has no universal reliable CPU temperature API.')
    summary=launch(options)
    rows=[]
    for job in summary['jobs']:
        car,track=job['car_id'],job['track_id']
        status=read_json(run_path(root,car,track)/'status.json',{})
        seconds=status.get('training_seconds',0)
        rate=status.get('steps',0)/seconds if seconds else 0.
        rows.append({'car':CARS[car].name,'track':TRACKS[track].spec.name,'steps':status.get('steps',0),
                     'steps_per_second':rate,'status':job['status'],'projected_steps_12_active_hours':int(rate*12*3600)})
    successful=[row['steps_per_second'] for row in rows if row['status']=='completed']
    total_steps=sum(row['steps'] for row in rows)
    aggregate=total_steps/max(summary['elapsed_seconds'],1.)
    advice=recommendation(successful,args.max_concurrent,args.n_envs,os.cpu_count() or 1)
    result=dict(summary,runs=rows,aggregate_steps_per_second=aggregate,recommendation=advice,n_envs=args.n_envs,
                projected_all_runs_steps_in_12_wall_hours=int(aggregate*12*3600))
    atomic_json(root/'benchmark_summary.json',result)
    print('\n=== COPY THIS 25-RUN BENCHMARK SUMMARY ===')
    for row in rows:
        print(f'{row["track"]:20} / {row["car"]:6}: {row["steps_per_second"]:8.1f} env steps/s; 12 active h ~{row["projected_steps_12_active_hours"]:,} steps; {row["status"]}')
    cpu=f'{summary["cpu_percent"]:.1f}%' if summary['cpu_percent'] is not None else 'unavailable'
    print(f'Aggregate including startup/waves: {aggregate:.1f} env steps/s; system CPU use: {cpu}')
    print(f'All drivers combined over 12 wall-clock hours at this throughput: ~{int(aggregate*43200):,} steps.')
    print(f'Root: {root.resolve()}\nSim: {summary["sim_version"]}\nRecommendation: {advice}')
    print('Check temperatures yourself; speed alone does not certify an overnight thermal setting. Wave runs take multiple ten-minute blocks.')
    if len(successful)!=25:
        print('INCOMPLETE: investigate failed/stopped jobs before using these projections.')
        raise SystemExit(1)


if __name__=='__main__': main()
