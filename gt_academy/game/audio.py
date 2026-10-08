"""Small precomputed synthesizer: no downloaded media, disk cache or threads."""
import numpy as np
import pygame
from .config import CLIENT


class Audio:
    def __init__(self,settings):
        self.settings=settings
        self.enabled=False
        self.current=None
        self.car=0
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(CLIENT.audio_rate,-16,2,512)
            self.rate=pygame.mixer.get_init()[0]
            pygame.mixer.set_num_channels(6)
            self.motor=pygame.mixer.Channel(0)
            self.tires=pygame.mixer.Channel(1)
            self.event=pygame.mixer.Channel(2)
            self.tones={}
            self.click=self.tone(900,.035,.3)
            self.beep=self.tone(660,.14,.4)
            self.go=self.tone(990,.25,.4)
            rng=np.random.default_rng(92)
            t=np.arange(int(self.rate*.24))/self.rate
            self.thump=self.sound((rng.uniform(-1,1,len(t))*.3+np.sin(2*np.pi*65*t)*.6)*np.exp(-t*20))
            t=np.arange(self.rate)/self.rate
            self.screech=self.sound((rng.uniform(-1,1,len(t))*.12+np.sin(2*np.pi*1700*t)*.12))
            self.tires.play(self.screech,loops=-1)
            self.tires.set_volume(0)
            self.enabled=True
        except (pygame.error,ValueError):
            self.enabled=False

    def sound(self,wave):
        pcm=np.asarray(np.clip(wave,-1,1)*16000,dtype=np.int16)
        return pygame.sndarray.make_sound(np.ascontiguousarray(np.column_stack((pcm,pcm))))

    def tone(self,frequency,duration,volume):
        t=np.arange(int(self.rate*duration))/self.rate
        return self.sound(np.sin(2*np.pi*frequency*t)*np.sin(np.pi*t/duration)**2*volume)

    def select_car(self,car):
        self.car=car
        if not self.enabled: return
        if car not in self.tones:
            bank=[]
            t=np.arange(int(self.rate*.2))/self.rate
            for level in range(40):
                hz=round((65+car*10+level*8)/5)*5
                phase=t*hz
                saw=2*(phase%1)-1
                wave=np.sin(2*np.pi*phase)*.40+saw*.08+np.sin(4*np.pi*phase)*.1
                bank.append(self.sound(wave))
            self.tones[car]=bank
        self.current=None

    def play(self,name):
        if self.enabled:
            # Wall contact may persist across physics ticks; avoid a harsh buzz.
            if name=='thump':
                now=pygame.time.get_ticks()
                if now-getattr(self,'last_impact_ms',-1000)<CLIENT.impact_interval_ms: return
                self.last_impact_ms=now
            self.event.set_volume(0 if self.settings['mute'] else self.settings['master']*self.settings['effects'])
            self.event.play(getattr(self,name))

    def update(self,state=None):
        if not self.enabled: return
        master=0 if self.settings['mute'] else self.settings['master']
        if state is None:
            self.motor.set_volume(0); self.tires.set_volume(0)
            return
        level=min(39,int(abs(state.vx)*.48+state.throttle*3))
        if self.current!=(self.car,level):
            self.motor.play(self.tones[self.car][level],loops=-1,fade_ms=20)
            self.current=(self.car,level)
        self.motor.set_volume(master*self.settings['engine']*(.25+.6*state.throttle))
        slip=max(abs(state.slip_front),abs(state.slip_rear))
        self.tires.set_volume(master*self.settings['effects']*min(.6,max(0,slip-.12))*min(1,abs(state.vx)/8))

    def close(self):
        if self.enabled: pygame.mixer.stop()
