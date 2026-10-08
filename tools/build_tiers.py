"""Export reliable opponent tiers without modifying training data."""
import argparse,json
from pathlib import Path
from gt_academy.rl.tiers import build,collect_evaluations


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path('runs'))
    parser.add_argument('--output',type=Path,default=Path('assets/ai'))
    parser.add_argument('--results',type=Path,help='Optional exhaustive evaluator results; otherwise use saved training evaluations')
    args=parser.parse_args()
    rows=json.loads(args.results.read_text(encoding='utf-8'))['results'] if args.results else collect_evaluations(args.root)
    manifest=build(args.root,args.output,rows)
    for key,tiers in manifest['pairs'].items():
        print(key+'  '+'  '.join(f'{name} {row["mean_lap"]:.2f}s' for name,row in tiers.items()))
    for warning in manifest['warnings']: print('WARNING:',warning)
    print(f'Exported 100 tier bundles from {len(rows)} evaluated checkpoints. Training files unchanged.')


if __name__=='__main__': main()
