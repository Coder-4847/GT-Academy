"""Opponents use the unchanged simulation and training action frequency."""
from collections import deque
from dataclasses import replace
import json
import pickle
import zipfile
import math
from pathlib import Path
import numpy as np
from ..cars import CARS
from ..tracks import TRACKS
from ..sim import Simulation,observation,require_version
from ..config import PHYSICS as P, ENVIRONMENT as E, TRACK
from .session import Session
from .config import CLIENT

TIERS=('Rookie','Pro','Champion','Legend')


class OpponentLibrary:
    def __init__(self,root=Path('assets/ai')):
        self.root=Path(root)

    def stats(self,car,track,tier):
        try:
            manifest=json.loads((self.root/'manifest.json').read_text(encoding='utf-8'))
            require_version(manifest.get('sim_version','missing'))
            row=manifest['pairs'][f'{track}:{car}'][tier]
            if not isinstance(row['sha256'],str) or len(row['sha256'])!=64:
                raise ValueError('Opponent manifest has an invalid checksum.')
            for name in ('mean_lap','completion_rate'):
                if not isinstance(row[name],(int,float)) or not math.isfinite(row[name]):
                    raise ValueError('Opponent manifest has invalid evaluation statistics.')
            path=(self.root/row['bundle']).resolve()
            if not path.is_relative_to(self.root.resolve()): raise ValueError('Invalid opponent bundle path')
            return row,path
        except (OSError,KeyError,TypeError,AttributeError,json.JSONDecodeError) as error:
            raise ValueError('Opponent unavailable. Install the AI library or rebuild it with tools.prepare_opponents.') from error

    def load(self,car,track,tier):
        from ..rl.runtime import configure_torch
        from ..rl.tiers import unpack_bundle
        from ..rl.storage import file_hash
        from ..rl.policy import Driver
        configure_torch()
        row,path=self.stats(car,track,tier)
        if file_hash(path)!=row['sha256']: raise ValueError('Opponent bundle checksum mismatch. Rebuild the AI library.')
        try:
            checkpoint=unpack_bundle(path,Path('player_data/ai_cache'),car,track)
            return Driver(checkpoint,car,track)
        except (zipfile.BadZipFile,pickle.UnpicklingError,EOFError,KeyError,TypeError,AttributeError) as error:
            raise ValueError('Opponent files are corrupt. Restore the AI library and clear player_data/ai_cache.') from error


def unlocked(medals,track,tier):
    if track>0 and f'{track-1}:Champion' not in medals: return False
    if tier=='Legend': return all(f'{t}:Champion' in medals for t in range(5))
    index=TIERS.index(tier)
    return index==0 or f'{track}:{TIERS[index-1]}' in medals


class Opponent:
    def __init__(self,driver,car,track,laps=3,imperfection=0.):
        self.driver,self.car_id,self.track_id=driver,car,track
        self.laps=laps
        self.imperfection=max(0.,min(1.,imperfection))
        self.rng=np.random.default_rng(1701)
        self.reset()

    def reset(self):
        self.sim=Simulation(CARS[self.car_id],TRACKS[self.track_id])
        self.previous=replace(self.sim.state)
        self.action=(0.,0.)
        self.queue=deque([(0.,0.)]*round(self.imperfection*3))
        self.elapsed=0.
        self.finish_time=None
        self.dnf=''
        self.offroad=self.stalled=0.
        self.inference_seconds=[]

    def step(self):
        if self.finish_time is not None or self.dnf: return
        from time import perf_counter
        if self.sim.state.ticks%E.frame_skip==0:
            started=perf_counter()
            action=self.driver.action(observation(self.sim.state,self.sim.car,self.sim.track))
            self.inference_seconds.append(perf_counter()-started)
            if len(self.inference_seconds)>600: self.inference_seconds.pop(0)
            noisy=(float(np.clip(action[0]+self.rng.normal(0,.035*self.imperfection),-1,1)),float(action[1]))
            self.queue.append(noisy); self.action=self.queue.popleft()
        self.previous=replace(self.sim.state)
        self.sim.step(self.action)
        self.elapsed+=P.dt
        state,lap=self.sim.state,self.sim.lap
        self.offroad=self.offroad+P.dt if abs(state.offset)>self.sim.track.spec.width/2+TRACK.kerb_width else 0.
        self.stalled=self.stalled+P.dt if state.vx<1 else 0.
        if state.impact_speed>=E.serious_impact: self.dnf='Wall impact'
        elif self.offroad>=E.offroad_timeout: self.dnf='Off track'
        elif self.stalled>=E.stalled_timeout: self.dnf='Stopped'
        elif self.elapsed>self.sim.track.length/E.reference_speed*E.time_limit_multiplier*self.laps: self.dnf='Time limit'
        if lap.completed_this_step and len(lap.lap_times)>=self.laps:
            self.finish_time=self.elapsed-lap.elapsed

    @property
    def distance(self):
        return len(self.sim.lap.lap_times)*self.sim.track.length+min(self.sim.track.length-.001,max(0,self.sim.lap.distance))


class RaceSession(Session):
    def __init__(self,car,track,mode,save,driver,rival_car,tier,laps=3,penalty=0.,imperfection=0.):
        super().__init__(car,track,mode,save)
        self.countdown=CLIENT.countdown
        self.tier=tier
        self.laps=max(1,min(5,int(laps)))
        self.penalty=max(0.,float(penalty))
        if mode=='Career': self.laps=3; self.penalty=0.; imperfection=0.
        self.opponent=Opponent(driver,rival_car,track,self.laps,imperfection)
        self.elapsed=0.
        self.player_finish=None
        self.result=''
        self.ghost=None
        self.history=[[],[]]

    def step(self,action):
        if self.finished: return
        if self.countdown>0:
            self.countdown=max(0,self.countdown-P.dt)
            if self.countdown<1e-9: self.countdown=0.
            return
        self.previous=replace(self.sim.state)
        self.sim.step(action); self.opponent.step(); self.elapsed+=P.dt
        for rows,distance in zip(self.history,(self.player_distance,self.opponent.distance)):
            if not rows or distance>rows[-1][0]: rows.append((distance,self.elapsed))
        lap=self.sim.lap
        if lap.completed_this_step and len(lap.lap_times)>=self.laps:
            self.player_finish=self.elapsed-lap.elapsed
            ai=self.opponent.finish_time
            self.result='Victory' if ai is None or self.player_finish<ai+self.penalty else ('Tie' if abs(self.player_finish-ai-self.penalty)<1e-6 else 'Defeat')
            self.finished=True
            key=f'{self.track_id}:{self.car_id}:{self.laps}'
            self.save.race_bests[key]=min(self.player_finish,self.save.race_bests.get(key,float('inf')))
            if self.result=='Victory' and self.mode=='Career':
                self.save.award(self.track_id,self.tier,self.player_finish)
            else: self.save.flush()
        if self.elapsed>self.sim.track.length/E.reference_speed*E.time_limit_multiplier*self.laps:
            self.finished=True; self.result='Time limit - DNF'

    @property
    def player_distance(self):
        return len(self.sim.lap.lap_times)*self.sim.track.length+min(self.sim.track.length-.001,max(0,self.sim.lap.distance))

    @property
    def position(self):
        if self.opponent.dnf: return 1
        return 1 if self.player_distance>=self.opponent.distance else 2

    @property
    def gap(self):
        """Measured passage-time difference at shared distance, not speed division."""
        from bisect import bisect_left
        if not all(self.history): return None
        distance=min(self.history[0][-1][0],self.history[1][-1][0])
        times=[]
        for rows in self.history:
            points=rows
            i=bisect_left(points,(distance,-float('inf')))
            if i>=len(points): return None
            if i==0: times.append(points[0][1]); continue
            a,b=points[i-1:i+1]
            times.append(a[1]+(b[1]-a[1])*(distance-a[0])/max(1e-9,b[0]-a[0]))
        return times[0]-times[1]-self.penalty

    def reset_to_track(self): return False

    def close(self): self.opponent.driver.close()


class AIGhostSession(Session):
    def __init__(self,car,track,save,driver,rival_car):
        super().__init__(car,track,'Time Trial',save)
        self.opponent=Opponent(driver,rival_car,track,1)

    def step(self,action):
        old=self.sim.lap.elapsed
        active=self.countdown==0 and not self.finished
        super().step(action)
        if active:
            self.opponent.step()
            if self.sim.lap.elapsed<old: self.opponent.reset()

    def close(self): self.opponent.driver.close()
