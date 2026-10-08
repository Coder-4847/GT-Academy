"""User-run ten-minute Atlas/Sunrise PPO learning check, isolated from real runs."""
import argparse
from datetime import datetime,timezone
from pathlib import Path
import sys
if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gt_academy.rl.runtime import configure_environment
configure_environment()
from gt_academy.rl.launcher import parser as launch_parser, launch
from gt_academy.rl.storage import read_json,run_path,atomic_json


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--minutes',type=float,default=10.)
    p.add_argument('--root',type=Path)
    p.add_argument('--n-envs',type=int,default=4)
    args=p.parse_args()
    if args.minutes<=0 or args.n_envs<=0: p.error('Minutes and environment count must be positive')
    root=args.root or Path('experiments')/('sanity_'+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_utc'))
    if any(root.glob('*/*/checkpoints')):
        p.error('Use a new --root for a fresh sanity test; keep existing experiments for comparison.')
    options=launch_parser().parse_args(['--root',str(root),'--cars','Atlas','--tracks','Sunrise_Oval',
        '--hours',str(args.minutes/60),'--max-concurrent','1','--n-envs',str(args.n_envs),
        '--checkpoint-steps','25000','--evaluate-every','0','--experiment'])
    summary=launch(options)
    status=read_json(run_path(root,0,0)/'status.json',{})
    evaluation=status.get('evaluation',{})
    passed=evaluation.get('completed_laps',0)>0 and all(job['status']=='completed' for job in summary['jobs'])
    result={'pass':passed,'root':str(root.resolve()),'steps':status.get('steps',0),
            'training_laps':status.get('training_laps',0),'evaluation':evaluation,
            'sim_version':summary['sim_version'],'elapsed_seconds':summary['elapsed_seconds']}
    atomic_json(root/'sanity_summary.json',result)
    print('\n=== COPY THIS SANITY SUMMARY ===')
    print('PASS: deterministic policy completed full laps.' if passed else 'NEEDS REVIEW: no verified lap completion; do not begin the overnight run yet.')
    print(f'Root: {root.resolve()}\nSteps: {result["steps"]:,}; training laps: {result["training_laps"]}')
    print(f'Evaluation: {evaluation}\nSim: {summary["sim_version"]}')
    print('Paste this summary; if a worker failed, add the last 30 lines of its worker.log.')
    print('This experiment does not freeze physics or overwrite overnight runs.')
    if not passed: raise SystemExit(1)


if __name__=='__main__': main()
