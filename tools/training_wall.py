"""Read-only 5×5 checkpoint playback, independent of all training workers."""
from pathlib import Path
import sys
import os
if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gt_academy.rl.runtime import configure_environment
configure_environment()
import argparse
import math
import time
import pygame
from gt_academy.config import TRAINING as T,ENVIRONMENT,PHYSICS
from gt_academy.cars import CARS
from gt_academy.tracks import TRACKS
from gt_academy.rl.runtime import configure_torch,set_priority
from gt_academy.rl.env import RacingEnv
from gt_academy.rl.policy import Driver
from gt_academy.rl.storage import latest_checkpoint,read_json,run_path


class Tile:
    def __init__(self,root: Path,car: int,track: int):
        self.run=run_path(root,car,track)
        self.car,self.track=car,track
        self.driver=None; self.env=None; self.raw=None
        self.loaded=None; self.message='waiting for checkpoint'
        self.checked=-float('inf'); self.steps=0; self.best=None

    def refresh(self):
        self.checked=time.monotonic()
        try:
            checkpoint=latest_checkpoint(self.run,car_id=self.car,track_id=self.track)
            status=read_json(self.run/'status.json',{})
            self.best=status.get('best_lap')
            if checkpoint is None or checkpoint==self.loaded: return
            driver=Driver(checkpoint,self.car,self.track)
            if self.driver: self.driver.close()
            if self.env: self.env.close()
            self.driver=driver; self.loaded=checkpoint
            self.env=RacingEnv(self.car,self.track,training=False)
            self.raw,_=self.env.reset(seed=0)
            self.steps=driver.metadata['steps']; self.message='checkpoint playback'
        except Exception as error:
            self.message='Cannot load: '+str(error).split('\n')[0]

    def step(self):
        if not self.driver: return
        try:
            self.raw,_,terminated,truncated,info=self.env.step(self.driver.action(self.raw))
            if terminated or truncated:
                self.raw,_=self.env.reset(seed=0)
                self.message='Last attempt: '+info['reason']
        except Exception as error:
            self.message='Playback error: '+str(error)
            self.driver.close(); self.driver=None

    def close(self):
        if self.driver: self.driver.close()
        if self.env: self.env.close()


class Wall:
    def __init__(self,root: Path,reload_seconds: float):
        configure_torch(); set_priority('below-normal')
        pygame.init()
        self.screen=pygame.display.set_mode((T.wall_width,T.wall_height),pygame.RESIZABLE)
        pygame.display.set_caption('GT Academy | Training Wall')
        self.font=pygame.font.SysFont('segoeui',15)
        self.small=pygame.font.SysFont('segoeui',12)
        self.tiles=[Tile(root,car,track) for track in range(5) for car in range(5)]
        self.reload_seconds=reload_seconds
        self.cursor=0; self.cache={}

    def backdrop(self,index: int,size: tuple):
        key=(index,size)
        if key in self.cache: return self.cache[key]
        track=TRACKS[index]
        surface=pygame.Surface(size)
        surface.fill(tuple(int(value*.35) for value in track.spec.color))
        low=track.left_wall.min(axis=0)-20
        high=track.right_wall.max(axis=0)+20
        # Both boundaries contribute to bounds, regardless of track winding.
        import numpy as np
        points=np.vstack((track.left_wall,track.right_wall))
        low=points.min(axis=0)-15; high=points.max(axis=0)+15
        scale=min(size[0]/(high[0]-low[0]),size[1]/(high[1]-low[1]))
        centre=(low+high)/2
        def project(point): return size[0]/2+(point[0]-centre[0])*scale,size[1]/2-(point[1]-centre[1])*scale
        road=[project(point) for point in track.center[::3]]
        pygame.draw.lines(surface,(100,111,112),True,road,max(2,round(track.spec.width*scale)))
        pygame.draw.aalines(surface,(145,155,151),True,road)
        self.cache[key]=(surface,project,scale)
        return self.cache[key]

    def draw(self):
        width,height=self.screen.get_size()
        self.screen.fill((22,27,30))
        speed=T.wall_fps*ENVIRONMENT.frame_skip*PHYSICS.dt
        self.screen.blit(self.font.render(f'GT ACADEMY   /   TRAINING WALL     Saved drivers at {speed:.1f}× speed; closing this window does not stop training.',True,(227,233,224)),(15,12))
        tile_width=width//5; tile_height=(height-45)//5
        for i,tile in enumerate(self.tiles):
            x=(i%5)*tile_width; y=45+(i//5)*tile_height
            rect=pygame.Rect(x+3,y+3,tile_width-6,tile_height-6)
            self.screen.set_clip(rect)
            self.screen.fill((32,39,41),rect)
            title=f'{TRACKS[tile.track].spec.name} / {CARS[tile.car].name}'
            self.screen.blit(self.small.render(title,True,(220,228,221)),(x+10,y+7))
            size=(tile_width-20,max(30,tile_height-66))
            background,project,scale=self.backdrop(tile.track,size)
            self.screen.blit(background,(x+10,y+27))
            if tile.env:
                s=tile.env.sim.state
                px,py=project((s.x,s.y)); pos=(x+10+px,y+27+py)
                pygame.draw.circle(self.screen,CARS[tile.car].color,pos,4)
                pygame.draw.line(self.screen,(241,237,222),pos,(pos[0]+math.cos(s.heading)*9,pos[1]-math.sin(s.heading)*9),2)
            best=f'{tile.best:.2f}s' if tile.best is not None else '—'
            self.screen.blit(self.small.render(f'{tile.steps:,} steps   /   best {best}',True,(210,222,216)),(x+10,y+tile_height-33))
            self.screen.blit(self.small.render(tile.message,True,(155,172,166)),(x+10,y+tile_height-18))
            self.screen.set_clip(None)
        pygame.display.flip()

    def run(self,frames: int=0,screenshot: Path|None=None):
        clock=pygame.time.Clock(); frame=0; running=True
        try:
            while running:
                clock.tick(T.wall_fps)
                for event in pygame.event.get():
                    if event.type==pygame.QUIT or (event.type==pygame.KEYDOWN and event.key==pygame.K_ESCAPE): running=False
                    elif event.type==pygame.VIDEORESIZE:
                        self.screen=pygame.display.set_mode((max(1000,event.w),max(750,event.h)),pygame.RESIZABLE)
                        self.cache.clear()
                # Stagger loading to one tile per frame. No readers ever write to runs.
                tile=self.tiles[self.cursor]; self.cursor=(self.cursor+1)%len(self.tiles)
                if time.monotonic()-tile.checked>=self.reload_seconds: tile.refresh()
                for tile in self.tiles: tile.step()
                self.draw(); frame+=1
                if frames and frame>=frames: break
            if screenshot:
                screenshot.parent.mkdir(parents=True,exist_ok=True)
                pygame.image.save(self.screen,str(screenshot))
        finally:
            for tile in self.tiles: tile.close()
            pygame.quit()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('runs'))
    p.add_argument('--reload-seconds',type=float,default=T.wall_reload_seconds)
    p.add_argument('--frames',type=int,default=0)
    p.add_argument('--smoke-test',action='store_true')
    p.add_argument('--screenshot',type=Path)
    args=p.parse_args()
    if args.reload_seconds<=0: p.error('Reload interval must be positive')
    if args.smoke_test:
        os.environ['SDL_VIDEODRIVER']='dummy'; os.environ['SDL_AUDIODRIVER']='dummy'
    Wall(args.root,args.reload_seconds).run(args.frames or (2 if args.smoke_test else 0),args.screenshot)


if __name__=='__main__': main()
