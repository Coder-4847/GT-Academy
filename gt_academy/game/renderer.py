"""Cached scenery, procedural car art and bounded presentation-only effects."""
from collections import OrderedDict
from math import cos,sin,exp,floor,ceil,hypot
from types import SimpleNamespace
import numpy as np
import pygame
import pygame.gfxdraw
from ..cars import CARS
from ..tracks import TRACKS
from .config import CLIENT as C
from .debug_viewer import DebugViewer


def polygon(surface,color,points):
    points=[(round(x),round(y)) for x,y in points]
    pygame.gfxdraw.filled_polygon(surface,points,color)
    pygame.gfxdraw.aapolygon(surface,points,color)


def car_art(surface,position,heading,scale,car_id,steering=0.,brake=0.,ghost=False):
    car=CARS[car_id]
    # Five distinct cosmetic silhouettes; all use the unchanged collision hull.
    noses=(2.05,1.8,2.0,2.3,2.1)
    widths=(.9,.94,.86,.82,.96)
    nose,width=noses[car_id],widths[car_id]
    ch,sh=cos(heading),sin(heading)
    def local(x,y):
        return (position[0]+(x*ch-y*sh)*scale,position[1]-(x*sh+y*ch)*scale)
    hull=[(nose,.55),(nose-.45,width),(-1.6,width),(-2,.55),(-2,-.55),(-1.6,-width),(nose-.45,-width),(nose,-.55)]
    if ghost:
        points=[local(x,y) for x,y in hull]
        pygame.draw.aalines(surface,(144,206,232),True,points)
        pygame.draw.aaline(surface,(144,206,232),local(-1.8,0),local(nose,0))
        return
    # Two translucent silhouettes soften the drop shadow.
    shadow=pygame.Surface((max(1,int(scale*6)),max(1,int(scale*6))),pygame.SRCALPHA)
    for spread,alpha in ((1.12,18),(1.,45)):
        points=[(shadow.get_width()/2+(x*ch-y*sh)*scale*spread,
                 shadow.get_height()/2-(x*sh+y*ch)*scale*spread) for x,y in hull]
        polygon(shadow,(0,0,0,alpha),points)
    surface.blit(shadow,(position[0]-shadow.get_width()/2+scale*.2,position[1]-shadow.get_height()/2+scale*.25))
    for axle in (car.front_arm,-car.rear_arm):
        for side in (-.92,.92):
            angle=steering if axle>0 else 0.
            points=[local(axle+x*cos(angle)-y*sin(angle),side+x*sin(angle)+y*cos(angle)) for x,y in ((-.38,-.16),(.38,-.16),(.38,.16),(-.38,.16))]
            polygon(surface,(12,18,23),points)
    polygon(surface,car.color,[local(x,y) for x,y in hull])
    polygon(surface,tuple(min(255,c+25) for c in car.color),[local(x,y) for x,y in ((.6,.62),(-.65,.64),(-.65,-.64),(.6,-.62))])
    for glass in (((.85,.65),(.35,.65),(.35,-.65),(.85,-.65)),((-.7,.62),(-1.25,.53),(-1.25,-.53),(-.7,-.62))):
        polygon(surface,(34,57,70),[local(x,y) for x,y in glass])
    if car_id in (1,2,4):
        pygame.draw.line(surface,(23,31,37),local(-1.8,-1.02),local(-1.8,1.02),max(2,round(scale*.16)))
    stripe=.13 if car_id!=3 else .23
    polygon(surface,(229,230,215),[local(x,y) for x,y in ((.95,-stripe),(nose-.12,-stripe),(nose-.12,stripe),(.95,stripe))])
    for side in (-.55,.55):
        pygame.draw.line(surface,(245,242,213),local(nose-.1,side-.12),local(nose-.1,side+.12),max(1,round(scale*.14)))
        pygame.draw.line(surface,(255,87,63) if brake>.1 else (132,61,55),local(-1.96,side-.15),local(-1.96,side+.15),max(1,round(scale*(.24 if brake>.1 else .12))))


class Renderer:
    def __init__(self):
        self.cache={}
        self.previews={}
        self.scene_buffers={}
        self.tiles=OrderedDict()
        self.track_id=None
        self.camera=np.zeros(2)
        self.zoom=C.zoom
        self.rng=np.random.default_rng(902)
        self.particles=[]
        self.shake=0.

    def prepare(self,track_id):
        if track_id not in self.cache:
            # Reuse the established cached track art without constructing a window.
            surface,origin,scale=DebugViewer.build_track(SimpleNamespace(sim=SimpleNamespace(track=TRACKS[track_id])))
            track=TRACKS[track_id]
            def point(p): return ((p[0]-origin[0])*scale,(origin[1]-p[1])*scale)
            for slot in range(6):
                p,_,i=track.grid(slot)
                tangent,normal=track.tangent[i],track.normal[i]
                points=[point(p+tangent*x+normal*y) for x,y in ((-2,-1),(2,-1),(2,1),(-2,1))]
                pygame.draw.lines(surface,(166,172,169),True,points,max(1,round(scale*.12)))
            self.cache[track_id]=(surface,origin,scale)
        self.track_id=track_id
        self.track_surface,self.origin,self.map_scale=self.cache[track_id]
        self.skids=pygame.Surface(self.track_surface.get_size(),pygame.SRCALPHA)
        self.particles=[]
        self.shake=0.

    def reset_camera(self,state):
        self.camera=np.array((state.x,state.y))
        self.zoom=C.zoom

    def map_point(self,x,y):
        return ((x-self.origin[0])*self.map_scale,(self.origin[1]-y)*self.map_scale)

    def effects_step(self,previous,state,quality):
        slip=max(abs(state.slip_front),abs(state.slip_rear))
        speed=hypot(state.vx,state.vy)
        offroad=not all(state.wheel_asphalt)
        if speed>3 and slip>C.slip_threshold and not offroad:
            for side in (-.8,.8):
                def wheel(s):
                    return self.map_point(s.x-cos(s.heading)*1.3-sin(s.heading)*side,
                                          s.y-sin(s.heading)*1.3+cos(s.heading)*side)
                pygame.draw.line(self.skids,(16,20,24,min(130,int(45+slip*80))),wheel(previous),wheel(state),
                                 max(1,round(self.map_scale*(.15+min(.3,slip)))))
        kind='dust' if offroad else 'smoke'
        if speed>5 and (offroad or slip>C.smoke_threshold) and state.ticks%3==0:
            self.emit(state,kind,2,quality)
        if state.wall_contact and state.impact_speed>1:
            self.emit(state,'spark',12,quality)
            self.shake=C.shake_seconds
        for particle in self.particles:
            particle[0]+=particle[2]/60; particle[1]+=particle[3]/60; particle[4]-=1/60
        self.particles=[p for p in self.particles if p[4]>0]
        self.shake=max(0,self.shake-1/60)

    def emit(self,state,kind,count,quality):
        cap=C.particle_limits[quality]
        for _ in range(min(count,cap-len(self.particles))):
            velocity=self.rng.normal(0,4 if kind=='spark' else 1,2)
            self.particles.append([state.x-cos(state.heading),state.y-sin(state.heading),
                                   *velocity,C.particle_lifetime,kind])

    def scene(self,target,state,car_id,dt,quality,ghost=None,rival=None):
        factor=C.quality_scales[quality]
        size=tuple(round(x*factor) for x in target.get_size())
        if factor==1:
            scene=target
        else:
            if size not in self.scene_buffers: self.scene_buffers[size]=pygame.Surface(size)
            scene=self.scene_buffers[size]
        width,height=size
        self.camera+=(np.array((state.x+cos(state.heading)*state.vx*C.lookahead,
                               state.y+sin(state.heading)*state.vx*C.lookahead))-self.camera)*(1-exp(-C.camera_response*dt))
        self.zoom+=(C.zoom/(1+abs(state.vx)/C.zoom_speed)-self.zoom)*(1-exp(-3*dt))
        zoom=self.zoom*factor
        shake=self.rng.uniform(-2,2,2)*self.shake/C.shake_seconds if self.shake else np.zeros(2)
        def project(x,y): return (width/2+(x-self.camera[0])*zoom+shake[0],height/2-(y-self.camera[1])*zoom+shake[1])
        scene.fill(tuple(int(c*.68) for c in TRACKS[self.track_id].spec.color))
        sw,sh=width/zoom*self.map_scale,height/zoom*self.map_scale
        cx,cy=self.map_point(*self.camera)
        area=pygame.Rect(floor(cx-sw/2)-2,floor(cy-sh/2)-2,ceil(sw)+4,ceil(sh)+4)
        area=area.clip(self.track_surface.get_rect())
        if area.width and area.height:
            dest=((area.x-(cx-sw/2))*zoom/self.map_scale+shake[0],(area.y-(cy-sh/2))*zoom/self.map_scale+shake[1])
            scaled=(max(1,round(area.width*zoom/self.map_scale)),max(1,round(area.height*zoom/self.map_scale)))
            # Reuse bounded crop surfaces to avoid a full allocation every frame.
            key=area.size
            tile=self.tiles.pop(key,None)
            if tile is None: tile=pygame.Surface(key).convert()
            self.tiles[key]=tile
            if len(self.tiles)>4: self.tiles.popitem(last=False)
            tile.blit(self.track_surface,(0,0),area)
            tile.blit(self.skids,(0,0),area)
            scene.blit(pygame.transform.smoothscale(tile,scaled),dest)
        for x,y,vx,vy,life,kind in self.particles:
            point=project(x,y)
            if kind=='spark':
                pygame.draw.aaline(scene,(243,196,113),point,project(x-vx*.06,y-vy*.06))
            else:
                radius=max(1,round(zoom*(.15+(C.particle_lifetime-life)*.8)))
                puff=pygame.Surface((radius*2+2,radius*2+2),pygame.SRCALPHA)
                color=(166,149,119) if kind=='dust' else (193,199,195)
                pygame.draw.circle(puff,(*color,int(75*life/C.particle_lifetime)),(radius+1,radius+1),radius)
                scene.blit(puff,(point[0]-radius,point[1]-radius))
        if ghost is not None: car_art(scene,project(ghost.x,ghost.y),ghost.heading,zoom,car_id,ghost.steering,ghost=True)
        if rival is not None:
            other,other_car,is_ghost=rival
            car_art(scene,project(other.x,other.y),other.heading,zoom,other_car,other.steering,other.brake,ghost=is_ghost)
            point=project(other.x,other.y)
            pygame.draw.circle(scene,(139,198,233),(round(point[0]),round(point[1])),max(3,round(zoom*2.6)),1)
        car_art(scene,project(state.x,state.y),state.heading,zoom,car_id,state.steering,state.brake)
        if state.vx>45 and quality<2:
            for i in range(8):
                y=(i*113+state.ticks*7)%height
                x=15 if i%2 else width-15
                pygame.draw.aaline(scene,(106,119,122),(x,y),(x,y+min(30,state.vx-40)))
        if factor!=1: pygame.transform.smoothscale(scene,target.get_size(),target)

    def preview(self,target,rect,track_id):
        key=(track_id,rect.size)
        if key not in self.previews:
            track=TRACKS[track_id]
            low=track.center.min(axis=0); high=track.center.max(axis=0)
            scale=min((rect.width-30)/(high[0]-low[0]),(rect.height-30)/(high[1]-low[1]))
            middle=(low+high)/2
            image=pygame.Surface(rect.size,pygame.SRCALPHA)
            points=[(rect.width/2+(x-middle[0])*scale,rect.height/2-(y-middle[1])*scale) for x,y in track.center[::3]]
            pygame.draw.lines(image,(62,79,90),True,points,max(3,round(track.spec.width*scale)))
            pygame.draw.aalines(image,(153,184,178),True,points)
            self.previews[key]=(image,scale,middle)
        image,scale,middle=self.previews[key]
        target.blit(image,rect)
        def point(x,y): return (rect.centerx+(x-middle[0])*scale,rect.centery-(y-middle[1])*scale)
        return point
