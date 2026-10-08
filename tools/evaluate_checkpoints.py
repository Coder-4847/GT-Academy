"""Evaluate every saved checkpoint using a bounded Windows-safe process pool."""
import argparse,json
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
from gt_academy.rl.runtime import configure_environment
configure_environment()


def evaluate_one(path,episodes):
    from gt_academy.rl.runtime import configure_torch
    from gt_academy.rl.storage import validate_checkpoint
    from gt_academy.rl.evaluate import evaluate
    configure_torch()
    metadata=validate_checkpoint(Path(path))
    return dict(evaluate(Path(path),episodes),checkpoint=str(Path(path).resolve()),
                car_id=metadata['car_id'],track_id=metadata['track_id'],sim_version=metadata['sim_version'],source='phase4 evaluation')


def main():
    from gt_academy.rl.tiers import outside_runs
    from gt_academy.sim import SIM_VERSION
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path('runs'))
    parser.add_argument('--output',type=Path,default=Path('artifacts/checkpoint-evaluations.json'))
    parser.add_argument('--workers',type=int,default=4)
    parser.add_argument('--episodes',type=int,default=3)
    parser.add_argument('--limit',type=int,default=0,help='Optional short verification subset')
    args=parser.parse_args()
    if args.workers<1 or args.episodes<3 or args.limit<0: parser.error('Use positive workers, at least three episodes and nonnegative limit')
    outside_runs(args.output,args.root)
    paths=sorted(args.root.glob('*/*/checkpoints/step_*'))
    if args.limit: paths=paths[:args.limit]
    data={'sim_version':SIM_VERSION,'results':[],'errors':[]}
    if args.output.exists():
        previous=json.loads(args.output.read_text(encoding='utf-8'))
        if previous.get('sim_version')==SIM_VERSION: data['results']=previous.get('results',[])
    done={r['checkpoint'] for r in data['results'] if r.get('episodes',0)>=args.episodes}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    def save():
        temp=args.output.with_suffix('.tmp'); temp.write_text(json.dumps(data,indent=2),encoding='utf-8'); temp.replace(args.output)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(evaluate_one,str(p.resolve()),args.episodes):p for p in paths if str(p.resolve()) not in done}
        for future in as_completed(futures):
            path=futures[future]
            try:
                row=future.result()
                data['results']=[r for r in data['results'] if r['checkpoint']!=row['checkpoint']]+[row]
                print(f'{path}: {row["completion_rate"]:.0%}',flush=True)
            except Exception as error:
                data['errors'].append({'checkpoint':str(path),'error':str(error)}); print(f'FAILED {path}: {error}',flush=True)
            save()
    save()
    print(f'{len(data["results"])} results, {len(data["errors"])} errors; {args.output}')


if __name__=='__main__': main()
