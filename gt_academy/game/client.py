"""Human and trained-opponent game client. Production training files stay untouched."""
import argparse
from dataclasses import replace
from math import ceil,sin
from pathlib import Path
from time import perf_counter
import os
import pygame
from ..cars import CARS
from ..tracks import TRACKS
from ..config import PHYSICS
from ..sim import SIM_VERSION
from .config import CLIENT as C
from .save import PlayerSave
from .replay import Replay
from .session import Session
from .racing import RaceSession,AIGhostSession,OpponentLibrary,unlocked,TIERS
from .controls import Controls
from .audio import Audio
from .renderer import Renderer,car_art
from .debug_viewer import interpolate_state


def time_label(seconds):
    return '--:--.---' if seconds is None else f'{int(seconds//60):02}:{seconds%60:06.3f}'


class Game:
    def __init__(self,save_path=Path('player_data/profile.json'),window=None):
        pygame.mixer.pre_init(C.audio_rate,-16,2,512)
        pygame.init()
        self.save=PlayerSave(save_path)
        self.settings=self.save.settings
        self.window_size=window or C.window
        self.display=pygame.display.set_mode(self.window_size,pygame.RESIZABLE)
        pygame.display.set_caption('GT Academy')
        self.canvas=pygame.Surface(C.canvas)
        self.presentation=None
        self.fonts={size:pygame.font.SysFont('segoeui',size,bold=size>=30) for size in (14,18,22,28,32,44,64,96)}
        self.renderer=Renderer()
        self.audio=Audio(self.settings)
        self.controls=Controls(self.settings)
        self.running=True
        self.screen='home'
        self.return_screen='home'
        self.mode='Time Trial'
        self.car_id=self.track_id=0
        self.session=None
        self.library=OpponentLibrary()
        self.replay=Replay()
        self.photo_requested=False
        self.buttons=[]
        self.sliders=[]
        self.focus=0
        self.rebinding=None
        self.dragging=None
        self.transition=0.
        self.clock=pygame.time.Clock()
        self.accumulator=0.
        self.visual_time=0.
        self.viewport=pygame.Rect(0,0,*self.display.get_size())
        self.message=''
        self.last_count=None
        if self.settings['fullscreen']: self.set_fullscreen(True)

    def text(self,text,pos,size=22,color=None):
        self.canvas.blit(self.fonts[size].render(str(text),True,color or C.foreground),pos)

    def button(self,label,rect,callback,selected=False):
        rect=pygame.Rect(rect)
        index=len(self.buttons)
        hovered=rect.collidepoint(self.mouse())
        color=(42,65,69) if selected or hovered or index==self.focus else C.panel
        pygame.draw.rect(self.canvas,color,rect,border_radius=10)
        if selected: pygame.draw.rect(self.canvas,C.accent,rect,width=2,border_radius=10)
        self.text(label,(rect.x+20,rect.y+(rect.height-28)/2),22)
        self.buttons.append((rect,callback))

    def mouse(self):
        x,y=pygame.mouse.get_pos()
        return ((x-self.viewport.x)*C.canvas[0]/max(1,self.viewport.width),
                (y-self.viewport.y)*C.canvas[1]/max(1,self.viewport.height))

    def go(self,screen):
        self.screen=screen
        self.focus=0
        self.buttons=[]
        self.transition=C.transition
        self.accumulator=0.
        if self.session: self.session.previous=replace(self.session.sim.state)
        self.audio.play('click')

    def choose_mode(self,mode):
        if mode in ('Race vs AI','Career') and not unlocked(self.save.medals,self.track_id,'Rookie'): self.track_id=0
        self.mode=mode; self.go('cars')

    def start(self):
        self.message=''
        racing=self.mode in ('Race vs AI','Career')
        tier=self.settings['rival_tier']
        if racing and not unlocked(self.save.medals,self.track_id,tier):
            self.message='This challenge is locked. Win the preceding Career challenge first.'
            return
        driver=None
        if racing or (self.mode=='Time Trial' and self.settings['ai_ghost']):
            self.text('Preparing rival...',(48,785),18,C.accent)
            self.display.blit(pygame.transform.smoothscale(self.canvas,self.display.get_size()),(0,0)); pygame.display.flip()
            try: driver=self.library.load(self.settings['rival_car'],self.track_id,tier)
            except (ValueError,OSError,RuntimeError) as error:
                self.message=str(error); return
        if self.session and hasattr(self.session,'close'): self.session.close()
        if racing:
            self.session=RaceSession(self.car_id,self.track_id,self.mode,self.save,driver,
                self.settings['rival_car'],tier,self.settings['race_laps'],self.settings['ai_penalty'],self.settings['ai_noise'])
        elif driver:
            self.session=AIGhostSession(self.car_id,self.track_id,self.save,driver,self.settings['rival_car'])
        else: self.session=Session(self.car_id,self.track_id,self.mode,self.save)
        self.renderer.prepare(self.track_id)
        self.renderer.reset_camera(self.session.sim.state)
        self.controls.steer=0.
        self.audio.select_car(self.car_id)
        self.last_count=None
        self.replay=Replay()
        self.replay.record(self.session)
        self.go('drive')

    def set_fullscreen(self,enabled):
        self.settings['fullscreen']=enabled
        self.display=pygame.display.set_mode((0,0) if enabled else self.window_size,
                                            pygame.FULLSCREEN if enabled else pygame.RESIZABLE)

    def settings_page(self):
        self.return_screen=self.screen
        self.go('settings')

    def reset(self):
        if not self.session: return
        if self.session.reset_to_track():
            self.controls.steer=0.
            self.accumulator=0.
            self.message='Returned to the racing surface'
        else:
            self.start()

    def events(self):
        for event in pygame.event.get():
            if event.type==pygame.QUIT:
                self.running=False
            elif event.type==pygame.WINDOWFOCUSLOST:
                if self.screen=='drive': self.go('pause')
                elif self.screen=='replay': self.replay.paused=True
            elif event.type==pygame.VIDEORESIZE and not self.settings['fullscreen']:
                self.window_size=(max(960,event.w),max(540,event.h))
                self.display=pygame.display.set_mode(self.window_size,pygame.RESIZABLE)
            elif event.type in (pygame.CONTROLLERDEVICEADDED,pygame.CONTROLLERDEVICEREMOVED):
                self.controls.refresh()
                if event.type==pygame.CONTROLLERDEVICEREMOVED and self.screen=='drive':
                    self.message='Controller disconnected. Keyboard is available.'
                    self.go('pause')
            elif event.type==pygame.CONTROLLERBUTTONDOWN:
                if event.button==pygame.CONTROLLER_BUTTON_START:
                    if self.screen=='drive': self.go('pause')
                    elif self.screen=='pause': self.go('drive')
                elif event.button==pygame.CONTROLLER_BUTTON_A and self.screen!='drive': self.activate()
                elif event.button==pygame.CONTROLLER_BUTTON_B: self.back()
                elif event.button==pygame.CONTROLLER_BUTTON_DPAD_DOWN: self.focus=(self.focus+1)%max(1,len(self.buttons))
                elif event.button==pygame.CONTROLLER_BUTTON_DPAD_UP: self.focus=(self.focus-1)%max(1,len(self.buttons))
            elif event.type==pygame.KEYDOWN:
                if self.rebinding:
                    if event.key==pygame.K_ESCAPE: self.rebinding=None
                    elif event.key not in (pygame.K_F11,pygame.K_F12,pygame.K_RETURN,pygame.K_TAB,pygame.K_p):
                        bindings=self.settings['bindings']
                        old=bindings[self.rebinding]
                        for name,key in bindings.items():
                            if key==event.key: bindings[name]=old
                        bindings[self.rebinding]=event.key
                        self.rebinding=None
                    continue
                if event.key==pygame.K_F12: self.photo_requested=self.screen in ('drive','pause','replay','results')
                elif self.screen=='replay' and event.key==pygame.K_SPACE: self.replay.paused=not self.replay.paused
                elif event.key==pygame.K_F11: self.set_fullscreen(not self.settings['fullscreen'])
                elif event.key==pygame.K_ESCAPE: self.back()
                elif self.screen=='drive':
                    if event.key==pygame.K_p: self.go('pause')
                    elif event.key==self.settings['bindings']['reset']: self.reset()
                elif event.key in (pygame.K_DOWN,pygame.K_TAB): self.focus=(self.focus+1)%max(1,len(self.buttons))
                elif event.key==pygame.K_UP: self.focus=(self.focus-1)%max(1,len(self.buttons))
                elif event.key in (pygame.K_RETURN,pygame.K_SPACE): self.activate()
            elif event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
                pos=self.mouse()
                for rect,name in self.sliders:
                    if rect.inflate(0,24).collidepoint(pos):
                        self.dragging=(rect,name); self.slide(pos)
                for index,(rect,callback) in enumerate(self.buttons):
                    if rect.collidepoint(pos):
                        self.focus=index; self.audio.play('click'); callback(); break
            elif event.type==pygame.MOUSEMOTION and self.dragging: self.slide(self.mouse())
            elif event.type==pygame.MOUSEBUTTONUP: self.dragging=None

    def slide(self,pos):
        rect,name=self.dragging
        self.settings[name]=max(0.,min(1.,(pos[0]-rect.x)/rect.width))

    def activate(self):
        if self.buttons:
            self.audio.play('click')
            self.buttons[self.focus%len(self.buttons)][1]()

    def back(self):
        if self.rebinding:
            self.rebinding=None
            return
        if self.screen=='replay': self.go('results')
        elif self.screen=='drive': self.go('pause')
        elif self.screen=='pause': self.go('drive')
        elif self.screen=='settings': self.save.flush(); self.go(self.return_screen)
        elif self.screen=='tracks': self.go('cars')
        elif self.screen=='rival': self.go('tracks')
        elif self.screen!='home': self.go('home')

    def update(self,elapsed):
        self.visual_time+=elapsed
        self.transition=max(0.,self.transition-elapsed)
        if self.screen=='replay':
            if self.replay.update(elapsed): self.go('results')
            self.audio.update(); return
        if self.screen!='drive': self.audio.update(); return
        self.accumulator+=min(elapsed,.1)
        session=self.session
        while self.accumulator>=PHYSICS.dt:
            countdown=ceil(session.countdown)
            if countdown!=self.last_count:
                if countdown>0: self.audio.play('beep')
                elif self.last_count is not None: self.audio.play('go')
                self.last_count=countdown
            action=self.controls.action(session.sim.state)
            session.step(action)
            if not session.countdown:
                self.renderer.effects_step(session.previous,session.sim.state,self.quality)
                self.replay.record(session)
                if session.sim.state.wall_contact and session.sim.state.impact_speed>1: self.audio.play('thump')
            self.accumulator-=PHYSICS.dt
            if session.finished:
                self.start_replay() if isinstance(session,RaceSession) else self.go('results')
                break
        self.audio.update(session.sim.state if self.screen=='drive' and not session.countdown else None)

    def start_replay(self):
        if len(self.replay.frames)<2:
            self.go('results'); return
        self.replay.start()
        self.renderer.reset_camera(self.replay.frames[0][0])
        self.go('replay')

    def draw_replay(self,dt,clean=False):
        state,other=self.replay.at()
        if state is None: return
        opponent=getattr(self.session,'opponent',None)
        rival=(other,opponent.car_id,False) if other is not None and opponent else None
        # Historical poses only; end-of-race particles would be out of time.
        particles,shake=self.renderer.particles,self.renderer.shake
        self.renderer.particles=[]; self.renderer.shake=0.
        self.renderer.scene(self.canvas,state,self.car_id,dt,self.quality,rival=rival)
        self.renderer.particles,self.renderer.shake=particles,shake
        if not clean:
            self.text('RACE REPLAY',(48,40),28,C.accent)
            self.text(f'{self.replay.playhead:04.1f} / {self.replay.duration:04.1f}s',(48,81),22)
            self.button('Resume' if self.replay.paused else 'Pause',(48,725,200,52),lambda:setattr(self.replay,'paused',not self.replay.paused))
            self.button('Results >',(1170,725,222,52),lambda:self.go('results'))
            self.text('Space: pause    F12: clean photo    Esc: results',(300,740),18)

    def save_photo(self):
        from datetime import datetime
        self.photo_requested=False
        try:
            folder=Path('player_data/screenshots'); folder.mkdir(parents=True,exist_ok=True)
            path=folder/(datetime.now().strftime('GT-Academy-%Y%m%d-%H%M%S-%f')+'.png')
            original=self.canvas.copy()
            if self.screen=='replay': self.draw_replay(0,clean=True)
            else: self.draw_drive(0,clean=True)
            pygame.image.save(self.canvas,str(path))
            self.canvas.blit(original,(0,0))
            self.message='Photo saved: '+path.name
        except (OSError,pygame.error) as error:
            self.message='Photo could not be saved: '+str(error)

    @property
    def quality(self): return ('High','Medium','Low').index(self.settings['quality'])

    def heading(self,kicker,title,subtitle=''):
        self.text(kicker.upper(),(48,35),18,C.accent)
        self.text(title,(48,70),44)
        self.text(subtitle,(50,130),22,C.muted)

    def draw_home(self):
        self.heading('GT Academy / driving club','Find your line.','Five circuits. Five cars. Your next personal best.')
        # An animated car display and circuit silhouette are generated in code.
        pygame.draw.rect(self.canvas,C.panel,(650,190,742,510),border_radius=18)
        self.renderer.preview(self.canvas,pygame.Rect(695,235,650,340),self.track_id)
        car_art(self.canvas,(1050,545),.35+sin(self.visual_time*.4)*.18,55,self.car_id,sin(self.visual_time)*.1)
        self.text(CARS[self.car_id].name.upper(),(705,625),32,CARS[self.car_id].color)
        self.text('DRIVE YOUR OWN LINE',(705,668),18,C.muted)
        self.button('Time Trial',(48,230,475,65),lambda:self.choose_mode('Time Trial'))
        self.text('Chase your own ghost or study an AI racing line.',(66,306),18,C.muted)
        self.button('Free Practice',(48,353,475,65),lambda:self.choose_mode('Free Practice'))
        self.button('Race vs AI',(48,453,226,65),lambda:self.choose_mode('Race vs AI'))
        self.button('Career',(291,453,232,65),lambda:self.choose_mode('Career'))
        self.button('Settings',(48,553,226,62),self.settings_page)
        self.button('Quit',(291,553,232,62),lambda:setattr(self,'running',False))
        self.text('WASD / arrows or controller. F12 saves a clean driving photo.',(48,713),18,C.muted)

    def draw_cars(self):
        self.heading(self.mode,'Choose your car','Same trusted handling. A different character in every garage bay.')
        stats=[('Speed','top_kph'),('Launch','launch_acceleration'),('Grip','grip_front'),('Brakes','brake_g'),('Handling','steer_degrees')]
        for i,car in enumerate(CARS):
            x=48+i*270
            rect=pygame.Rect(x,192,254,455)
            pygame.draw.rect(self.canvas,C.panel,rect,border_radius=12)
            if self.car_id==i: pygame.draw.rect(self.canvas,C.accent,rect,2,border_radius=12)
            self.text(car.name,(x+20,212),32,car.color)
            self.text(car.archetype,(x+20,256),18,C.muted)
            car_art(self.canvas,(x+127,345),.5+sin(self.visual_time*.7)*.15,31,i,sin(self.visual_time)*.12)
            for row,(label,attribute) in enumerate(stats):
                y=425+row*36
                maximum=max(getattr(c,attribute) for c in CARS)
                self.text(label,(x+20,y),18,C.muted)
                pygame.draw.rect(self.canvas,(53,64,71),(x+113,y+6,118,7),border_radius=3)
                pygame.draw.rect(self.canvas,car.color,(x+113,y+6,round(118*getattr(car,attribute)/maximum),7),border_radius=3)
            self.button('Selected' if self.car_id==i else 'Select',(x+14,657,226,48),lambda i=i:setattr(self,'car_id',i),self.car_id==i)
        self.button('Back',(48,736,190,48),lambda:self.go('home'))
        self.button('Choose circuit  >',(1120,736,272,48),lambda:self.go('tracks'))

    def draw_tracks(self):
        self.heading(self.mode,'Choose your circuit',f'{CARS[self.car_id].name} / '+('Win each Champion in Career to open the next circuit.' if self.mode in ('Race vs AI','Career') else 'All circuits open for practice and time trials.'))
        for i,track in enumerate(TRACKS):
            x=48+i*270
            rect=pygame.Rect(x,192,254,455)
            pygame.draw.rect(self.canvas,C.panel,rect,border_radius=12)
            if i==self.track_id: pygame.draw.rect(self.canvas,C.accent,rect,2,border_radius=12)
            self.text(f'0{i+1}',(x+18,215),18,C.accent)
            self.text(track.spec.name,(x+18,251),22)
            self.renderer.preview(self.canvas,pygame.Rect(x+10,310,234,180),i)
            self.text(f'{track.length/1000:.1f} km',(x+18,513),32)
            self.text('PERSONAL BEST',(x+18,570),14,C.muted)
            self.text(time_label(self.save.best(self.car_id,i)),(x+18,594),22)
            available=self.mode not in ('Race vs AI','Career') or unlocked(self.save.medals,i,'Rookie')
            self.button(('Selected' if i==self.track_id else 'Select') if available else 'Locked',(x+14,657,226,48),lambda i=i,available=available:self.select_track(i,available),i==self.track_id)
        self.button('Back',(48,736,190,48),lambda:self.go('cars'))
        self.button('Start driving  >' if self.mode=='Free Practice' else 'Choose rival  >',(1120,736,272,48),self.start if self.mode=='Free Practice' else lambda:self.go('rival'))

    def select_track(self,track,available):
        if available:
            self.track_id=track
            if self.mode in ('Race vs AI','Career') and not unlocked(self.save.medals,track,self.settings['rival_tier']):
                self.settings['rival_tier']='Rookie'
            self.message=''
        else: self.message='Beat the previous circuit Champion in Career to unlock this track.'

    def draw_rival(self):
        ghost=self.mode=='Time Trial'
        career=self.mode=='Career'
        self.heading(self.mode,'Pick your rival' if not ghost else 'Pick a ghost',f'{CARS[self.car_id].name} at {TRACKS[self.track_id].spec.name}')
        for i,car in enumerate(CARS):
            x=48+i*270
            car_art(self.canvas,(x+115,248),.45,26,i)
            self.button(car.name,(x,308,250,52),lambda i=i:self.settings.update(rival_car=i),i==self.settings['rival_car'])
        for i,tier in enumerate(TIERS):
            available=ghost or unlocked(self.save.medals,self.track_id,tier)
            won=f'{self.track_id}:{tier}' in self.save.medals
            label=tier+(' - won' if won else '' if available else ' - locked')
            self.button(label,(48+i*338,408,322,58),lambda tier=tier,available=available:self.select_tier(tier,available),self.settings['rival_tier']==tier)
        try:
            stats,_=self.library.stats(self.settings['rival_car'],self.track_id,self.settings['rival_tier'])
            self.text(f'Evaluated mean lap {time_label(stats["mean_lap"])} / {stats["completion_rate"]:.0%} completion',(48,486),22,C.muted)
            if stats.get('race_validation'):
                self.text(f'{stats["race_validation"]["completed_laps"]} continuous race laps verified',(950,490),18,C.accent)
        except ValueError as error: self.text(str(error),(48,486),18,(243,179,128))
        if ghost:
            self.button('AI ghost: '+('On' if self.settings['ai_ghost'] else 'Off - personal best'),(48,548,630,60),lambda:self.settings.update(ai_ghost=not self.settings['ai_ghost']))
            self.text('AI ghosts reset on your start-line crossing. They never collide.',(48,635),22,C.muted)
        elif career:
            self.text('Career: three laps, no handicap or added AI mistakes.',(48,553),28)
            self.text('Rookie > Pro > Champion > next circuit. All five Champions unlock Legend.',(48,610),22,C.muted)
            self.text('Choose any rival car. A win here saves a medal and unlocks your next challenge.',(48,648),18,C.accent)
        else:
            self.button(f'Laps: {self.settings["race_laps"]}',(48,548,260,56),lambda:self.settings.update(race_laps=self.settings['race_laps']%5+1))
            self.button(f'AI penalty: +{self.settings["ai_penalty"]:g}s',(330,548,360,56),lambda:self.settings.update(ai_penalty=(self.settings['ai_penalty']+5)%65))
            self.text('AI mistakes / reaction delay',(48,642),22)
            rect=pygame.Rect(430,655,400,8)
            pygame.draw.rect(self.canvas,(61,75,84),rect,border_radius=4)
            pygame.draw.circle(self.canvas,C.accent,(round(rect.x+rect.width*self.settings['ai_noise']),rect.y+4),10)
            self.sliders.append((rect,'ai_noise'))
            self.text(f'{self.settings["ai_noise"]:.0%}',(853,642),22,C.muted)
            self.text('Custom races do not award Career medals.',(950,569),18,C.muted)
        self.button('Back',(48,736,190,48),lambda:self.go('tracks'))
        self.button('Start driving  >',(1120,736,272,48),self.start)

    def select_tier(self,tier,available):
        if available: self.settings['rival_tier']=tier; self.message=''
        else: self.message='Win the preceding Career tier. Legend needs all five Champion medals.'

    def draw_settings(self):
        self.heading('Preferences','Make it yours','Settings and personal bests save locally. Escape returns to the previous screen.')
        self.text('GRAPHICS',(48,197),18,C.accent)
        for i,name in enumerate(('High','Medium','Low')):
            self.button(name,(48+i*166,235,150,54),lambda name=name:self.settings.update(quality=name),self.settings['quality']==name)
        self.button('Fullscreen: '+('On' if self.settings['fullscreen'] else 'Off'),(48,315,480,54),lambda:self.set_fullscreen(not self.settings['fullscreen']))
        self.button('Steering assist: '+('On' if self.settings['assist'] else 'Off'),(48,387,480,54),lambda:self.settings.update(assist=not self.settings['assist']))
        self.text('Gentle countersteer input; car physics stays the same.',(50,450),18,C.muted)
        self.text('AUDIO',(48,509),18,C.accent)
        for i,name in enumerate(('master','engine','effects')):
            y=555+i*53
            self.text(name.title(),(48,y-12),22)
            rect=pygame.Rect(195,y,270,8)
            pygame.draw.rect(self.canvas,(61,75,84),rect,border_radius=4)
            pygame.draw.circle(self.canvas,C.accent,(round(rect.x+rect.width*self.settings[name]),y+4),10)
            self.text(f'{self.settings[name]:.0%}',(481,y-12),18,C.muted)
            self.sliders.append((rect,name))
        self.button('Muted' if self.settings['mute'] else 'Mute',(48,708,480,50),lambda:self.settings.update(mute=not self.settings['mute']))
        self.text('CONTROLS',(735,197),18,C.accent)
        for i,(name,key) in enumerate(self.settings['bindings'].items()):
            label='Press a key... (Esc cancels)' if self.rebinding==name else f'{name.title()}     {pygame.key.name(key).upper()}'
            self.button(label,(735,235+i*66,657,52),lambda name=name:setattr(self,'rebinding',name))
        self.text('Arrow keys always work. Rebinding swaps duplicate keys.',(735,588),18,C.muted)
        self.text('Xbox: left stick / RT throttle / LT brake / Start pause',(735,620),18,C.muted)
        self.text('Menus: D-pad + A / B, or mouse / arrows + Enter',(735,652),18,C.muted)
        self.text('Audio ready' if self.audio.enabled else 'No audio device - playing silently',(735,691),18,C.muted)
        self.button('Save & return',(1120,736,272,48),self.back)

    def draw_drive(self,dt,clean=False):
        session=self.session; sim=session.sim
        state=interpolate_state(session.previous,sim.state,self.accumulator/PHYSICS.dt) if self.screen=='drive' else sim.state
        ghost=session.ghost.at(sim.lap.elapsed) if session.ghost and session.mode=='Time Trial' else None
        rival=None
        opponent=getattr(session,'opponent',None)
        if opponent:
            other=interpolate_state(opponent.previous,opponent.sim.state,self.accumulator/PHYSICS.dt) if self.screen=='drive' else opponent.sim.state
            rival=(other,opponent.car_id,isinstance(session,AIGhostSession))
            if isinstance(session,AIGhostSession): ghost=None
        self.renderer.scene(self.canvas,state,self.car_id,dt if self.screen=='drive' else 0,self.quality,ghost,rival)
        if clean: return
        if self.screen in ('pause','results'):
            overlay=pygame.Surface(C.canvas,pygame.SRCALPHA)
            overlay.fill((8,15,22,200)); self.canvas.blit(overlay,(0,0))
            return
        pygame.draw.rect(self.canvas,C.background,(24,22,650,110),border_radius=12)
        self.text(TRACKS[self.track_id].spec.name,(44,36),28)
        self.text(session.mode,(44,78),18,C.accent)
        target=session.laps if isinstance(session,RaceSession) else C.trial_laps if session.mode=='Time Trial' else None
        self.text('LAP '+str(min(target or 999,len(sim.lap.lap_times)+1))+(f' / {target}' if target else ''),(348,35),18,C.muted)
        self.text(time_label(sim.lap.elapsed),(348,65),32)
        pygame.draw.rect(self.canvas,C.background,(24,654,325,132),border_radius=12)
        self.text(f'{abs(state.vx)*3.6:03.0f}',(45,650),64)
        self.text('KM/H',(191,694),18,C.muted)
        self.text(CARS[self.car_id].name.upper(),(47,748),18,CARS[self.car_id].color)
        self.text('BEST  '+time_label(self.save.best(self.car_id,self.track_id)),(386,740),22)
        rect=pygame.Rect(1180,22,236,172)
        pygame.draw.rect(self.canvas,C.background,rect,border_radius=12)
        point=self.renderer.preview(self.canvas,rect,self.track_id)
        pygame.draw.circle(self.canvas,C.accent,point(state.x,state.y),5)
        if opponent:
            pygame.draw.circle(self.canvas,(139,198,233),point(opponent.sim.state.x,opponent.sim.state.y),4)
            self.text('AI / '+CARS[opponent.car_id].name,(1190,204),18,(139,198,233))
        if isinstance(session,RaceSession):
            gap=session.gap
            self.text(f'ON TRACK  P{session.position} / 2',(700,35),28,C.accent)
            status='AI DNF: '+opponent.dnf if opponent.dnf else ('AI finished' if opponent.finish_time else (f'Gap {gap:+.2f}s' if gap is not None else 'Standing start'))
            self.text(status,(700,80),22)
            if session.penalty: self.text(f'AI +{session.penalty:g}s penalty included in gap',(700,116),18,C.muted)
        if not sim.lap.valid:
            self.text('Lap invalid - cross the start line for another attempt',(44,146),22,(243,179,128))
        elif session.ghost and session.mode=='Time Trial':
            delta=session.ghost.delta(sim.lap.elapsed,sim.lap.distance)
            if delta is not None: self.text(f'{delta:+.2f}s vs best',(44,146),22,C.accent if delta<=0 else (243,179,128))
        self.text('F12 photo / Esc pause / '+pygame.key.name(self.settings['bindings']['reset']).upper()+(': reset to track' if self.mode=='Free Practice' else ': restart session'),(885,748),18)
        if session.countdown:
            label=str(ceil(session.countdown))
            self.text(label,(680,310),96)
            self.text('Get ready',(654,424),28)

    def draw_pause(self):
        self.heading('Take a breath','Paused',self.message or 'Your lap is paused. Resume when you are ready.')
        self.button('Resume',(48,220,460,64),lambda:self.go('drive'))
        self.button('Restart session',(48,309,460,64),self.start)
        self.button('Settings',(48,398,460,64),self.settings_page)
        self.button('Finish session',(48,487,460,64),lambda:self.go('results'))
        self.button('Main menu',(48,576,460,64),lambda:self.go('home'))

    def draw_results(self):
        session=self.session
        if isinstance(session,RaceSession):
            self.heading('Race complete',session.result or 'Session ended',f'{CARS[self.car_id].name} vs {CARS[session.opponent.car_id].name} / {session.tier} / {session.mode}')
            self.text('YOU',(60,209),22,C.accent)
            self.text('RIVAL',(720,209),22,(139,198,233))
            for x,sim in ((60,session.sim),(720,session.opponent.sim)):
                for i,seconds in enumerate(sim.lap.lap_times):
                    self.text(f'Lap {i+1}     {time_label(seconds)}',(x,258+i*48),28)
            self.text('Total: '+(time_label(session.player_finish) if session.player_finish else 'DNF / incomplete'),(60,529),28)
            other=session.opponent.finish_time
            self.text('Total: '+(time_label(other+session.penalty) if other is not None else 'DNF / incomplete'),(720,529),28)
            if session.penalty: self.text(f'Includes +{session.penalty:g}s handicap',(720,577),18,C.muted)
            if session.mode=='Career' and session.result=='Victory':
                self.text('Medal saved. Your next Career challenge is unlocked.',(60,619),22,C.accent)
            elif session.opponent.dnf: self.text('Rival retired: '+session.opponent.dnf,(60,619),22,C.muted)
            self.button('Watch replay',(1060,617,332,52),self.start_replay)
            self.button('Race again',(48,701,360,65),self.start)
            self.button('Next challenge',(436,701,360,65),lambda:self.go('tracks'))
            self.button('Main menu',(824,701,360,65),lambda:self.go('home'))
            return
        self.heading('Session complete','A new benchmark.' if session.new_best else 'Keep finding time.',
                     f'{CARS[self.car_id].name} / {TRACKS[self.track_id].spec.name} / {session.mode}')
        laps=session.sim.lap.lap_times
        for i,seconds in enumerate(laps[-6:]):
            self.text(f'LAP {max(0,len(laps)-6)+i+1:02}',(60,225+i*52),22,C.muted)
            self.text(time_label(seconds),(260,225+i*52),28)
        if not laps: self.text('No valid laps completed this session.',(60,236),28)
        self.text('PERSONAL BEST',(860,249),18,C.accent)
        self.text(time_label(self.save.best(self.car_id,self.track_id)),(856,288),44)
        self.text('Saved best-lap ghost ready' if self.save.record(self.car_id,self.track_id) else 'Complete a valid Time Trial lap to save a ghost.',(860,360),18,C.muted)
        self.button('Drive again',(48,701,360,65),self.start)
        self.button('Change car / circuit',(436,701,360,65),lambda:self.go('cars'))
        self.button('Main menu',(824,701,360,65),lambda:self.go('home'))

    def draw(self,dt):
        self.buttons=[]; self.sliders=[]
        if self.screen not in ('drive','pause','results','replay'): self.canvas.fill(C.background)
        if self.screen in ('drive','pause','results'):
            self.draw_drive(dt)
            if self.screen=='pause': self.draw_pause()
            elif self.screen=='results': self.draw_results()
        elif self.screen=='replay': self.draw_replay(dt)
        else:
            getattr(self,'draw_'+self.screen)()
        if self.photo_requested: self.save_photo()
        if self.save.warning: self.text(self.save.warning,(48,785),14,(243,179,128))
        elif self.message and self.screen not in ('drive','pause'): self.text(self.message[:145],(48,787),14,(243,179,128))
        if self.transition>0:
            overlay=pygame.Surface(C.canvas,pygame.SRCALPHA)
            overlay.fill((*C.background,int(100*self.transition/C.transition)))
            self.canvas.blit(overlay,(0,0))
        w,h=self.display.get_size()
        scale=min(w/C.canvas[0],h/C.canvas[1])
        size=(round(C.canvas[0]*scale),round(C.canvas[1]*scale))
        self.viewport=pygame.Rect((w-size[0])//2,(h-size[1])//2,*size)
        if size!=(w,h): self.display.fill(C.background)
        if self.presentation is None or self.presentation.get_size()!=size:
            self.presentation=pygame.Surface(size)
        pygame.transform.smoothscale(self.canvas,size,self.presentation)
        self.display.blit(self.presentation,self.viewport)
        pygame.display.flip()

    def run(self,frames=0,screenshot=None,smoke=False):
        previous=perf_counter(); count=0
        if smoke: self.controls.action=lambda state:(0.,0.)
        try:
            while self.running:
                if not smoke: self.clock.tick(C.fps)
                now=perf_counter(); elapsed=PHYSICS.dt if smoke else min(.1,now-previous); previous=now
                self.events(); self.update(elapsed); self.draw(elapsed)
                count+=1
                if frames and count>=frames: break
            if screenshot:
                screenshot.parent.mkdir(parents=True,exist_ok=True)
                pygame.image.save(self.display,str(screenshot))
        finally:
            if self.session and hasattr(self.session,'close'): self.session.close()
            self.save.flush(); self.audio.close(); pygame.quit()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke-test',action='store_true')
    parser.add_argument('--frames',type=int,default=0)
    parser.add_argument('--screenshot',type=Path)
    parser.add_argument('--save-file',type=Path,default=Path('player_data/profile.json'))
    parser.add_argument('--mode',choices=('menu','trial','practice'),default='menu')
    parser.add_argument('--car',type=int,choices=range(1,6),default=1)
    parser.add_argument('--track',type=int,choices=range(1,6),default=1)
    args=parser.parse_args()
    if args.smoke_test:
        os.environ['SDL_VIDEODRIVER']='dummy'; os.environ['SDL_AUDIODRIVER']='dummy'
    # A CLI override must never put player data into the protected training tree.
    runs=Path('runs').resolve()
    if args.save_file.resolve().is_relative_to(runs): parser.error('Player saves must be outside runs.')
    game=Game(args.save_file)
    game.car_id=args.car-1; game.track_id=args.track-1
    if args.mode!='menu':
        game.mode='Time Trial' if args.mode=='trial' else 'Free Practice'; game.start()
    print(f'GT Academy / Phase 5 / simulation {SIM_VERSION}')
    game.run(args.frames or (5 if args.smoke_test else 0),args.screenshot,args.smoke_test)


if __name__=='__main__': main()
