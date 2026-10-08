"""Plot deterministic best lap versus environment steps from a run's CSV history."""
import argparse
import csv
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('run',type=Path,help='Example: runs/sunrise_oval/atlas')
    p.add_argument('--output',type=Path)
    args=p.parse_args()
    history=args.run/'logs'/'lap_history.csv'
    if not history.exists(): p.error(f'No evaluation history yet: {history}')
    with history.open(newline='',encoding='utf-8') as stream:
        rows=list(csv.DictReader(stream))
    samples=[(int(row['steps']),float(row['best_lap'])) for row in rows if row.get('best_lap')]
    if not samples: p.error('No completed evaluation lap yet; wait for learning to progress')
    import matplotlib
    if args.output: matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    steps,times=zip(*sorted(samples))
    best=[]; current=float('inf')
    for value in times:
        current=min(current,value); best.append(current)
    fig,ax=plt.subplots(figsize=(9,5))
    ax.plot(steps,times,'.',alpha=.4,label='Checkpoint lap')
    ax.plot(steps,best,color='#487d72',label='Best so far')
    ax.set(xlabel='Environment steps',ylabel='Lap time (seconds)',title=str(args.run))
    ax.grid(alpha=.2); ax.legend(); fig.tight_layout()
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        fig.savefig(args.output,dpi=180)
        print(args.output.resolve())
    else: plt.show()
    plt.close(fig)


if __name__=='__main__': main()
