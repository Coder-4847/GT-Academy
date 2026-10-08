"""Real exported policy checks, game screenshots and inference timings; no training."""
import argparse,json,os
from pathlib import Path
from time import perf_counter
import numpy as np
from gt_academy.game.racing import OpponentLibrary,Opponent


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--all-tiers',action='store_true')
    parser.add_argument('--screens',action='store_true')
    args=parser.parse_args()
    output=Path('artifacts/phase4'); output.mkdir(parents=True,exist_ok=True)
    library=OpponentLibrary()
    results=[]
    tiers=('Rookie','Pro','Champion','Legend') if args.all_tiers else ('Legend',)
    for track in range(5):
        for car in range(5):
            for tier in tiers:
                driver=library.load(car,track,tier)
                opponent=Opponent(driver,car,track,3)
                try:
                    while opponent.finish_time is None and not opponent.dnf: opponent.step()
                    times=opponent.inference_seconds
                    row={'car_id':car,'track_id':track,'tier':tier,'laps':opponent.sim.lap.lap_times,
                         'finish':opponent.finish_time,'dnf':opponent.dnf,
                         'inference_p95_ms':float(np.percentile(times,95))*1000 if times else None}
                    results.append(row)
                    print(f'{track}:{car} {tier}: {len(row["laps"])}/3 laps {row["dnf"]}',flush=True)
                finally: driver.close()
                (output/'race-validation.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    if args.screens: screens(output)


def screens(output):
    os.environ['SDL_VIDEODRIVER']='dummy'; os.environ['SDL_AUDIODRIVER']='dummy'
    import pygame
    from gt_academy.game.client import Game
    game=Game(output/'verification-profile.json')
    try:
        game.mode='Race vs AI'; game.settings['race_laps']=1
        for screen in ('home','tracks','rival'):
            game.go(screen); game.transition=0; game.draw(1/60)
            pygame.image.save(game.display,str(output/(screen+'.png')))
        game.start(); game.transition=0; game.session.countdown=0
        times=[]
        for _ in range(240):
            start=perf_counter()
            game.session.step((.12,.55))
            game.renderer.effects_step(game.session.previous,game.session.sim.state,game.quality)
            game.draw(1/60)
            times.append((perf_counter()-start)*1000)
        pygame.image.save(game.display,str(output/'race.png'))
        game.go('results'); game.transition=0; game.draw(1/60)
        pygame.image.save(game.display,str(output/'race-results.png'))
        game.mode='Career'; game.go('rival'); game.transition=0; game.draw(1/60)
        pygame.image.save(game.display,str(output/'career.png'))
        game.mode='Time Trial'; game.settings['ai_ghost']=True; game.start()
        for _ in range(240): game.session.step((0,0))
        game.transition=0; game.draw(1/60)
        pygame.image.save(game.display,str(output/'ai-ghost.png'))
        metrics={'median_frame_ms':float(np.median(times)),'p95_frame_ms':float(np.percentile(times,95)),
                 'note':'240 offscreen race frames with a real policy; not a live display FPS guarantee.'}
        (output/'frame-times.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8')
        print(metrics)
    finally:
        if game.session and hasattr(game.session,'close'): game.session.close()
        game.audio.close(); pygame.quit()


if __name__=='__main__': main()
