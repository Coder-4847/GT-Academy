"""Phase 1 driving laboratory. Rendering reads state and owns all wall-clock use."""
import argparse
from math import cos, sin, degrees, hypot, exp, pi, floor, ceil
from dataclasses import replace
from time import perf_counter
from pathlib import Path
import os
import numpy as np
import pygame
from ..cars import CARS
from ..tracks import TRACKS
from ..config import PHYSICS, TRACK, SENSORS, VIEWER as V
from ..sim import Simulation, SIM_VERSION, observation
from ..sim.physics import approach
from ..sim.sensors import ray_distances, RAY_ANGLES


def interpolate_state(previous, current, alpha):
    """Presentation only: never write interpolated values into the simulator."""
    result = replace(current)
    for name in ('x', 'y', 'vx', 'vy', 'steering'):
        setattr(result, name, getattr(previous, name)*(1-alpha)+getattr(current, name)*alpha)
    delta = (current.heading-previous.heading+pi)%(2*pi)-pi
    result.heading = previous.heading+delta*alpha
    return result


class DebugViewer:
    def __init__(self, car: int = 0, track: int = 0):
        pygame.init()
        self.screen = pygame.display.set_mode((V.width,V.height),pygame.RESIZABLE)
        pygame.display.set_caption('GT Academy | Driving laboratory')
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont('segoeui',18)
        self.small = pygame.font.SysFont('segoeui',14)
        self.title = pygame.font.SysFont('segoeui',28,bold=True)
        self.large = pygame.font.SysFont('segoeui',56,bold=True)
        self.car_id,self.track_id = car,track
        self.rays,self.forces,self.relative = False,False,False
        self.diagnostics = False
        self.frame_dt = 1/V.fps
        self.render_state = None
        self.overview,self.paused,self.fullscreen = False,False,False
        self.keyboard_steer = 0.
        self.accumulator = 0.
        self.running = True
        self.select()

    def select(self) -> None:
        self.sim = Simulation(CARS[self.car_id],TRACKS[self.track_id])
        self.camera = np.array((self.sim.state.x,self.sim.state.y))
        self.keyboard_steer = 0.
        self.accumulator = 0.
        self.previous_state = replace(self.sim.state)
        self.render_state = None
        self.zoom = V.pixels_per_metre
        self.track_surface,self.map_origin,self.map_scale = self.build_track()

    def build_track(self) -> tuple[pygame.Surface,np.ndarray,float]:
        track = self.sim.track
        bounds = np.vstack((track.left_wall,track.right_wall))
        low,high = bounds.min(axis=0)-30,bounds.max(axis=0)+30
        scale = min(4.0,5000/max(high-low))
        size = np.ceil((high-low)*scale).astype(int)
        surface = pygame.Surface(tuple(size))
        base = track.spec.color
        surface.fill(tuple(int(c*0.68) for c in base))
        # Deterministic scenery stays out of the simulation and observation data.
        rng = np.random.default_rng(1907)
        for _ in range(18000):
            x,y = rng.integers((0,0),size)
            tone = rng.integers(-8,9)
            color = tuple(max(0,min(255,int(c*.68)+int(tone))) for c in base)
            pygame.draw.circle(surface,color,(int(x),int(y)),int(rng.integers(1,4)))

        def project(points):
            return [(float((x-low[0])*scale),float((high[1]-y)*scale)) for x,y in points]

        def ribbon(left,right,color):
            # Quads fill the annulus without incorrectly filling its infield.
            lp,rp = project(left),project(right)
            for i in range(len(lp)):
                j = (i+1)%len(lp)
                pygame.draw.polygon(surface,color,(lp[i],lp[j],rp[j],rp[i]))

        ribbon(track.left_wall,track.right_wall,(143,133,108))
        ribbon(track.left,track.right,(57,64,72))
        # Road grain, trees and their shadows are baked once per selection.
        for i in range(0,track.count,3):
            point = track.center[i]+track.normal[i]*rng.uniform(-track.spec.width*.45,track.spec.width*.45)
            pygame.draw.circle(surface,(65,72,79),project([point])[0],max(1,int(scale*.12)))
        for i in range(0,track.count,19):
            for side in (-1,1):
                point=track.center[i]+side*track.normal[i]*(track.spec.width/2+TRACK.runoff+rng.uniform(7,20))
                _,offset,_=track.nearest(*point)
                if abs(offset)<track.spec.width/2+TRACK.runoff+4:
                    continue
                x,y=project([point])[0]
                radius=int(scale*rng.uniform(1.7,3.0))
                pygame.draw.circle(surface,(35,47,38),(int(x+radius*.5),int(y+radius*.5)),radius)
                pygame.draw.circle(surface,(46,76,54),(int(x),int(y)),radius)
                pygame.draw.circle(surface,(64,96,65),(int(x-radius*.2),int(y-radius*.2)),int(radius*.7))
        for side,mask in ((1,track.kerb_left),(-1,track.kerb_right)):
            inner = track.center + track.normal*side*(track.spec.width/2)
            outer = inner + track.normal*side*TRACK.kerb_width
            ip,op = project(inner),project(outer)
            for i in range(track.count):
                if mask[i]:
                    j=(i+1)%track.count
                    color=(234,231,212) if (i//4)%2 else (204,77,63)
                    pygame.draw.polygon(surface,color,(ip[i],ip[j],op[j],op[i]))
        for edge in (track.left,track.right):
            pygame.draw.aalines(surface,(172,177,172),True,project(edge))
        for wall in (track.left_wall,track.right_wall):
            pygame.draw.lines(surface,(196,205,204),True,project(wall),max(1,round(scale*0.5)))
        start = track.center[0]
        for row in range(2):
            for column in range(round(track.spec.width)):
                p = start + track.normal[0]*(column-track.spec.width/2) + track.tangent[0]*row
                corners=(p,p+track.normal[0],p+track.normal[0]+track.tangent[0],p+track.tangent[0])
                pygame.draw.polygon(surface,(215,215,203) if (row+column)%2 else (45,50,52),project(corners))
        return surface,np.array((low[0],high[1])),scale

    def text(self, text: str, pos: tuple, color=None, font=None) -> None:
        self.screen.blit((font or self.font).render(text,True,color or V.text),pos)

    def world(self, x: float, y: float) -> tuple[float,float]:
        return (self.viewport.centerx+(x-self.camera[0])*self.zoom,
                self.viewport.centery-(y-self.camera[1])*self.zoom)

    def draw_car(self) -> None:
        s,c = self.render_state or self.sim.state,self.sim.car
        ch,sh = cos(s.heading),sin(s.heading)

        def local(x,y):
            return self.world(s.x+ch*x-sh*y,s.y+sh*x+ch*y)

        hull = [(2.1,.67),(1.5,.92),(-1.6,.92),(-2.1,.6),(-2.1,-.6),(-1.6,-.92),(1.5,-.92),(2.1,-.67)]
        polygon=[local(x,y) for x,y in hull]
        shadow=[(x+3,y+4) for x,y in polygon]
        pygame.draw.polygon(self.screen,(35,39,39),shadow)
        pygame.draw.polygon(self.screen,c.color,polygon)
        pygame.draw.aalines(self.screen,(240,221,193),True,polygon)
        pygame.draw.polygon(self.screen,(39,54,62),[local(x,y) for x,y in ((.7,.65),(.25,.7),(.25,-.7),(.7,-.65))])
        pygame.draw.polygon(self.screen,(65,78,81),[local(x,y) for x,y in ((-.6,.65),(-1.25,.58),(-1.25,-.58),(-.6,-.65))])
        for axle in (c.front_arm,-c.rear_arm):
            for side in (-c.hull_radius,c.hull_radius):
                angle=s.steering if axle>0 else 0
                points=[]
                for x,y in ((-.38,-.14),(.38,-.14),(.38,.14),(-.38,.14)):
                    points.append(local(axle+x*cos(angle)-y*sin(angle),side+x*sin(angle)+y*cos(angle)))
                pygame.draw.polygon(self.screen,(24,29,31),points)
        for side in (-.6,.6):
            pygame.draw.line(self.screen,(245,96,75) if s.brake>.1 else (113,68,61),local(-2,side-.15),local(-2,side+.15),max(1,round(self.zoom*.15)))
        # Bonnet stripe, roof highlight, headlights and rear wing.
        pygame.draw.polygon(self.screen,(235,235,221),[local(x,y) for x,y in ((.8,-.12),(2,-.12),(2,.12),(.8,.12))])
        pygame.draw.line(self.screen,(230,223,208),local(-.4,-.5),local(-.4,.5),max(1,round(self.zoom*.1)))
        pygame.draw.line(self.screen,(25,32,39),local(-1.85,-1),local(-1.85,1),max(2,round(self.zoom*.2)))
        for side in (-.55,.55):
            pygame.draw.line(self.screen,(242,247,219),local(1.95,side-.12),local(1.95,side+.12),max(2,round(self.zoom*.15)))
        if self.forces:
            for arm,force,slip in ((c.front_arm,s.force_front,s.slip_front),(-c.rear_arm,s.force_rear,s.slip_rear)):
                pygame.draw.line(self.screen,(136,207,174),local(arm,0),local(arm,force*V.force_scale),2)
                pygame.draw.line(self.screen,(230,169,117),local(arm,0),local(arm+4*cos(slip),4*sin(slip)),2)
            for arm in (-c.hull_offset,0,c.hull_offset):
                pygame.draw.circle(self.screen,(165,175,174),local(arm,0),max(1,round(c.hull_radius*self.zoom)),1)

    def draw_scene(self) -> None:
        w,h = self.screen.get_size()
        panel_width = min(350,max(290,int(w*.25))) if self.diagnostics else 0
        self.viewport=pygame.Rect(0,80,w-panel_width,h-150)
        s,t = self.render_state or self.sim.state,self.sim.track
        if self.overview:
            low=t.center.min(axis=0); high=t.center.max(axis=0)
            self.camera=(low+high)/2
            self.zoom=min(self.viewport.width/(high[0]-low[0]+70),self.viewport.height/(high[1]-low[1]+70))
        else:
            self.zoom+=(V.pixels_per_metre/(1+abs(s.vx)/170)-self.zoom)*(1-exp(-3*self.frame_dt))
            target=np.array((s.x+cos(s.heading)*s.vx*.35,s.y+sin(s.heading)*s.vx*.35))
            self.camera+=(target-self.camera)*(1-exp(-V.camera_response*self.frame_dt))
        self.screen.set_clip(self.viewport)
        self.screen.fill(tuple(int(c*.68) for c in t.spec.color),self.viewport)
        # Crop the cached map before scaling: the cost depends on window size,
        # not the full track texture size.
        source_w=self.viewport.width/self.zoom*self.map_scale
        source_h=self.viewport.height/self.zoom*self.map_scale
        cx=(self.camera[0]-self.map_origin[0])*self.map_scale
        cy=(self.map_origin[1]-self.camera[1])*self.map_scale
        wanted=pygame.Rect(floor(cx-source_w/2)-1,floor(cy-source_h/2)-1,ceil(source_w)+3,ceil(source_h)+3)
        clipped=wanted.clip(self.track_surface.get_rect())
        if clipped.width and clipped.height:
            dest=(self.viewport.left+(clipped.left-(cx-source_w/2))*self.zoom/self.map_scale,
                  self.viewport.top+(clipped.top-(cy-source_h/2))*self.zoom/self.map_scale)
            size=(max(1,round(clipped.width*self.zoom/self.map_scale)),max(1,round(clipped.height*self.zoom/self.map_scale)))
            self.screen.blit(pygame.transform.smoothscale(self.track_surface.subsurface(clipped),size),dest)
        if self.rays:
            for ray,distance in zip(RAY_ANGLES,ray_distances(s,t)):
                end=self.world(s.x+cos(s.heading+ray)*distance,s.y+sin(s.heading+ray)*distance)
                pygame.draw.aaline(self.screen,(139,177,175),self.world(s.x,s.y),end)
                pygame.draw.circle(self.screen,(198,211,192),end,2)
        self.draw_car()
        self.screen.set_clip(None)
        if self.diagnostics:
            self.draw_panel(self.viewport.right,80,panel_width,h-150)
        else:
            self.draw_hud()
        if self.paused:
            self.text('PAUSED',(self.viewport.left+28,110),font=self.title)

    def draw_hud(self):
        s,c,t,l=self.render_state or self.sim.state,self.sim.car,self.sim.track,self.sim.lap
        bottom=self.viewport.bottom
        box=pygame.Rect(24,bottom-132,260,108)
        pygame.draw.rect(self.screen,(20,29,38),box,border_radius=12)
        pygame.draw.rect(self.screen,c.color,(24,bottom-132,5,108),border_radius=2)
        self.text(f'{hypot(s.vx,s.vy)*3.6:03.0f}',(43,bottom-130),font=self.large)
        self.text('KM/H',(177,bottom-91),V.secondary,self.small)
        self.text(c.name.upper(),(45,bottom-54),c.color,self.small)
        pygame.draw.rect(self.screen,(52,64,71),(150,bottom-48,108,5),border_radius=2)
        pygame.draw.rect(self.screen,(242,109,86) if s.brake>.1 else (117,221,177),
                         (150,bottom-48,int(108*max(s.throttle,s.brake)),5),border_radius=2)
        self.text(f'LAP {len(l.lap_times)+1:02}   {self.time_label(l.elapsed)}',(28,100),font=self.title)
        self.text(f'BEST  {self.time_label(l.best)}',(30,137),V.secondary,self.small)
        if not l.valid:
            self.text('LAP INVALID - cross start to retry',(30,161),(242,173,117),self.small)
        rect=pygame.Rect(self.viewport.right-222,100,198,150)
        pygame.draw.rect(self.screen,(20,29,38),rect,border_radius=12)
        low=t.center.min(axis=0); high=t.center.max(axis=0)
        scale=min((rect.width-32)/(high[0]-low[0]),(rect.height-32)/(high[1]-low[1]))
        middle=(low+high)/2
        def point(x,y):
            return (rect.centerx+(x-middle[0])*scale,rect.centery-(y-middle[1])*scale)
        pygame.draw.lines(self.screen,(89,113,125),True,[point(x,y) for x,y in t.center[::5]],3)
        pygame.draw.circle(self.screen,c.color,point(s.x,s.y),5)

    @staticmethod
    def time_label(seconds) -> str:
        return '--:--.---' if seconds is None else f'{int(seconds//60):02}:{seconds%60:06.3f}'

    def draw_panel(self, x: int, y: int, width: int, height: int) -> None:
        pygame.draw.rect(self.screen,V.panel,(x,y,width,height))
        s,c,t,l=self.sim.state,self.sim.car,self.sim.track,self.sim.lap
        x+=24; y+=18
        self.text('LIVE TELEMETRY',(x,y),V.secondary,self.small)
        self.text(f'{hypot(s.vx,s.vy)*3.6:03.0f}',(x,y+24),font=self.large)
        self.text('km/h',(x+130,y+63),V.secondary)
        rows=[('Car',f'{c.name} / {c.archetype}'),
              ('Front / rear slip',f'{degrees(s.slip_front):+.1f} / {degrees(s.slip_rear):+.1f} deg'),
              ('Lateral load',f'{s.lateral_acceleration/PHYSICS.gravity:+.2f} g'),
              ('Surface F / R',f'{s.surface_front} / {s.surface_rear}'),
              ('Throttle / brake',f'{s.throttle:.0%} / {s.brake:.0%}'),
              ('Steering',f'{degrees(s.steering):+.1f} deg'),
              ('Lap',f'{len(l.lap_times)+1}   |   next gate {l.next_gate or "START"}'),
              ('Current',self.time_label(l.elapsed)),('Best',self.time_label(l.best)),
              ('Lap status','VALID' if l.valid else 'INVALID — cross start to retry')]
        y+=115
        for label,value in rows:
            self.text(label,(x,y),V.secondary,self.small)
            self.text(value,(x,y+18),font=self.small if len(value)>30 else self.font)
            y+=47
        if self.relative and y+95<self.screen.get_height()-70:
            obs=observation(s,c,t)
            self.text(f'Offset {s.offset:+.2f} m   heading {obs[20]*180:+.1f}°',(x,y),V.secondary,self.small)
            self.text(f'Progress {s.progress:.0f} / {t.length:.0f} m',(x,y+22),V.secondary,self.small)
        if s.wall_contact:
            self.text(f'WALL  {s.impact_speed*3.6:.1f} km/h impact',(x,self.screen.get_height()-102),(238,164,125),self.small)

    def draw(self) -> None:
        self.screen.fill(V.background)
        self.text('GT ACADEMY',(24,13),font=self.title)
        self.text('TIME ATTACK  /  FREE DRIVE',(25,48),V.secondary,self.small)
        self.text(self.sim.track.spec.name,(310,20),font=self.title)
        self.text(f'{self.sim.track.length/1000:.1f} km  /  {self.sim.track.spec.width:g} m wide',(312,52),V.secondary,self.small)
        self.draw_scene()
        w,h=self.screen.get_size()
        self.text('WASD / arrows  drive     1–5  car     T  track     R  reset     M  map     P  pause',(24,h-57),V.text,self.small)
        self.text('Tab  telemetry     V  rays     F  forces     H  relative data     F11  fullscreen     Esc  quit',(24,h-32),V.secondary,self.small)
        self.text(f'SIM {SIM_VERSION[:12]}',(w-160,h-32),V.secondary,self.small)
        pygame.display.flip()

    def events(self) -> None:
        for event in pygame.event.get():
            if event.type==pygame.QUIT:
                self.running=False
            elif event.type==pygame.WINDOWFOCUSLOST:
                self.paused=True
                self.accumulator=0.
                self.previous_state=replace(self.sim.state)
            elif event.type==pygame.VIDEORESIZE and not self.fullscreen:
                self.screen=pygame.display.set_mode((max(1000,event.w),max(800,event.h)),pygame.RESIZABLE)
            elif event.type==pygame.KEYDOWN:
                if event.key==pygame.K_ESCAPE:
                    self.running=False
                elif pygame.K_1<=event.key<=pygame.K_5:
                    self.car_id=event.key-pygame.K_1; self.select()
                elif event.key==pygame.K_t:
                    self.track_id=(self.track_id+1)%len(TRACKS); self.select()
                elif event.key==pygame.K_r:
                    self.select()
                elif event.key==pygame.K_p:
                    self.paused=not self.paused; self.accumulator=0.
                    self.previous_state=replace(self.sim.state)
                elif event.key==pygame.K_m:
                    self.overview=not self.overview
                    if not self.overview:
                        self.camera=np.array((self.sim.state.x,self.sim.state.y))
                        self.zoom=V.pixels_per_metre/(1+abs(self.sim.state.vx)/170)
                elif event.key==pygame.K_TAB:
                    self.diagnostics=not self.diagnostics
                elif event.key==pygame.K_v:
                    self.rays=not self.rays
                elif event.key==pygame.K_f:
                    self.forces=not self.forces
                elif event.key==pygame.K_h:
                    self.relative=not self.relative
                elif event.key==pygame.K_F11:
                    self.fullscreen=not self.fullscreen
                    self.screen=pygame.display.set_mode((0,0) if self.fullscreen else (V.width,V.height),pygame.FULLSCREEN if self.fullscreen else pygame.RESIZABLE)

    def run(self, frames: int = 0, screenshot: Path | None = None, smoke: bool = False) -> None:
        frame=0
        last_time=perf_counter()
        while self.running:
            if not smoke:
                self.clock.tick(V.fps)
            now=perf_counter()
            elapsed=min(now-last_time,.1) if not smoke else PHYSICS.dt
            last_time=now
            self.frame_dt=elapsed
            self.events()
            if not self.paused:
                self.accumulator+=elapsed
                keys=pygame.key.get_pressed()
                target=float(keys[pygame.K_LEFT] or keys[pygame.K_a])-float(keys[pygame.K_RIGHT] or keys[pygame.K_d])
                pedal=float(keys[pygame.K_UP] or keys[pygame.K_w])-float(keys[pygame.K_DOWN] or keys[pygame.K_s])
                while self.accumulator>=PHYSICS.dt:
                    self.keyboard_steer=approach(self.keyboard_steer,target,V.keyboard_rate*PHYSICS.dt)
                    self.previous_state=replace(self.sim.state)
                    self.sim.step((self.keyboard_steer,pedal))
                    self.accumulator-=PHYSICS.dt
            self.render_state=interpolate_state(self.previous_state,self.sim.state,self.accumulator/PHYSICS.dt) if not self.paused else replace(self.sim.state)
            self.draw()
            frame+=1
            if frames and frame>=frames:
                break
        if screenshot:
            screenshot.parent.mkdir(parents=True,exist_ok=True)
            pygame.image.save(self.screen,str(screenshot))
        pygame.quit()


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--car',type=int,choices=range(1,6),default=1)
    parser.add_argument('--track',type=int,choices=range(1,6),default=1)
    parser.add_argument('--frames',type=int,default=0)
    parser.add_argument('--screenshot',type=Path)
    parser.add_argument('--smoke-test',action='store_true')
    parser.add_argument('--map',action='store_true')
    args=parser.parse_args()
    if args.smoke_test:
        os.environ['SDL_VIDEODRIVER']='dummy'
        os.environ['SDL_AUDIODRIVER']='dummy'
    print(f'Simulation version: {SIM_VERSION}')
    viewer=DebugViewer(args.car-1,args.track-1)
    viewer.overview=args.map
    viewer.run(args.frames or (3 if args.smoke_test else 0),args.screenshot,args.smoke_test)


if __name__=='__main__':
    main()
