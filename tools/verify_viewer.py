"""Offscreen viewer integration bug check; writes a five-track contact sheet."""
import os
os.environ['SDL_VIDEODRIVER']='dummy'
os.environ['SDL_AUDIODRIVER']='dummy'

from pathlib import Path
import sys
if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

import pygame
from gt_academy.game.debug_viewer import DebugViewer


def main() -> None:
    viewer=DebugViewer()
    output=Path('artifacts')
    output.mkdir(exist_ok=True)
    sheet=pygame.Surface((1440,900*3))
    sheet.fill((22,27,30))
    for track in range(5):
        for car in range(5):
            viewer.track_id=track
            viewer.car_id=car
            viewer.select()
            for step in range(30):
                viewer.sim.step((.1,.5))
            viewer.overview=True
            viewer.draw()
            if car==0:
                image=pygame.transform.smoothscale(viewer.screen,(720,450))
                sheet.blit(image,((track%2)*720,(track//2)*450))
            print(f'PASS viewer: {viewer.sim.track.spec.name} / {viewer.sim.car.name}')
    # Event wiring also gets exercised, independently of keyboard focus.
    for key in (pygame.K_t,pygame.K_3,pygame.K_r,pygame.K_v,pygame.K_f,pygame.K_h,pygame.K_p,pygame.K_p):
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN,key=key))
        viewer.events()
    assert viewer.car_id==2 and viewer.track_id==0
    pygame.image.save(sheet.subsurface((0,0,1440,1350)),str(output/'track-contact-sheet.png'))
    viewer.overview=False
    viewer.rays=viewer.forces=viewer.relative=True
    for _ in range(90):
        viewer.sim.step((.05,.65))
    viewer.draw()
    pygame.image.save(viewer.screen,str(output/'debug-drive.png'))
    viewer.rays=viewer.forces=viewer.relative=False
    viewer.draw()
    pygame.image.save(viewer.screen,str(output/'arcade-drive.png'))
    pygame.quit()
    print('25 combinations and input events passed. Offscreen bug check, not an FPS claim.')


if __name__=='__main__':
    main()
