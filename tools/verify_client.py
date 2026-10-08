"""Offscreen Phase 3 bug checks and screenshots, never a training job."""
import os
os.environ['SDL_VIDEODRIVER']='dummy'
os.environ['SDL_AUDIODRIVER']='dummy'
import json
from pathlib import Path
from time import perf_counter
import numpy as np
import pygame
from gt_academy.game.client import Game
from gt_academy.sim import SIM_VERSION


def main():
    output=Path('artifacts/phase3'); output.mkdir(parents=True,exist_ok=True)
    game=Game(output/'verification-profile.json')
    timings={}
    try:
        for screen in ('home','cars','tracks','settings'):
            game.go(screen); game.transition=0
            game.draw(1/60)
            pygame.image.save(game.display,str(output/f'{screen}.png'))
        game.mode='Free Practice'
        for track in range(5):
            game.track_id=track
            for car in range(5):
                game.car_id=car; game.start(); game.transition=0
                for _ in range(30): game.session.step((.05,.6))
                game.draw(1/60)
                if car==track:
                    pygame.image.save(game.display,str(output/f'track-{track+1}.png'))
                print(f'PASS car {car+1} / track {track+1}',flush=True)
        game.car_id=0; game.track_id=0; game.start(); game.transition=0
        state=game.session.sim.state
        for quality in ('High','Medium','Low'):
            game.settings['quality']=quality
            samples=[]
            for _ in range(120):
                start=perf_counter()
                game.session.step((.1,.6))
                # Effect stress state is a copy; it cannot alter the session.
                from dataclasses import replace
                effect=replace(game.session.sim.state,slip_rear=.5,wall_contact=True,impact_speed=3)
                game.renderer.effects_step(game.session.previous,effect,game.quality)
                game.draw(1/60)
                samples.append((perf_counter()-start)*1000)
            timings[quality]={'median_ms':round(float(np.median(samples)),2),'p95_ms':round(float(np.percentile(samples,95)),2)}
        game.settings['quality']='High'; game.draw(1/60)
        pygame.image.save(game.display,str(output/'effects.png'))
        for screen in ('pause','results'):
            game.go(screen); game.transition=0; game.draw(1/60)
            pygame.image.save(game.display,str(output/f'{screen}.png'))
        result={'sim_version':SIM_VERSION,'combinations':25,'frame_work':timings,
                'note':'Offscreen bug check, not live display FPS or an audible/controller hardware test.'}
        (output/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result,indent=2))
    finally:
        game.audio.close(); pygame.quit()


if __name__=='__main__': main()
