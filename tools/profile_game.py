"""Reproducible High-quality race frame workload; never trains or writes runs."""
import argparse
import json
import os
from pathlib import Path
from time import perf_counter


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label',default='after')
    parser.add_argument('--frames',type=int,default=360)
    parser.add_argument('--window',action='store_true',help='Use the real display instead of offscreen SDL')
    args=parser.parse_args()
    if args.frames<60: parser.error('Use at least 60 measured frames')
    if Path(args.label).name!=args.label: parser.error('Label must be a filename component')
    if not args.window: os.environ['SDL_VIDEODRIVER']='dummy'
    os.environ['SDL_AUDIODRIVER']='dummy'
    import numpy as np
    import pygame
    from gt_academy.game.client import Game
    output=Path('artifacts/phase5'); output.mkdir(parents=True,exist_ok=True)
    game=Game(output/'benchmark-profile.json')
    results=[]
    try:
        game.settings.update(quality='High',rival_tier='Rookie',rival_car=0)
        game.save.medals={f'{i}:Champion':100 for i in range(5)}
        game.mode='Race vs AI'
        for track in range(5):
            game.track_id=track; game.start()
            if game.screen!='drive': raise RuntimeError(game.message)
            game.session.countdown=0
            game.controls.action=lambda state:game.session.opponent.action
            measurements=[]
            for frame in range(args.frames+60):
                pygame.event.pump()
                if frame%30==0: game.renderer.emit(game.session.sim.state,'dust',12,0)
                begin=perf_counter()
                game.update(1/60); game.draw(1/60)
                if frame>=60: measurements.append((perf_counter()-begin)*1000)
            results.append(dict(track=track,median_ms=float(np.median(measurements)),
                p95_ms=float(np.percentile(measurements,95)),p99_ms=float(np.percentile(measurements,99)),
                over_budget_percent=100*sum(x>1000/60 for x in measurements)/len(measurements)))
            print(results[-1],flush=True)
        report=dict(display=pygame.display.get_driver(),resolution=game.display.get_size(),quality='High',frames_per_track=args.frames,
            note='Uncapped frame workload with real AI and particles, audio disabled. Real-display pacing and live audio require a play-through.',results=results)
        (output/(args.label+'.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
    finally:
        if game.session and hasattr(game.session,'close'): game.session.close()
        game.audio.close(); pygame.quit()


if __name__=='__main__': main()
