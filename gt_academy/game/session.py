"""Human session and state ghosts; simulation and lap rules stay authoritative."""
from bisect import bisect_right
from dataclasses import replace
from math import pi
from ..cars import CARS
from ..tracks import TRACKS
from ..config import PHYSICS
from ..sim import Simulation
from ..sim.state import CarState, LapState
from .config import CLIENT


class Ghost:
    def __init__(self,record):
        self.rows=record['ghost']
        self.times=[r[0] for r in self.rows]
        # Progress is monotonic for timing comparisons, even after a correction.
        self.progress=[]
        peak=0.
        for row in self.rows:
            peak=max(peak,row[5]); self.progress.append(peak)

    def at(self,seconds):
        if seconds<0 or seconds>self.times[-1]: return None
        i=max(0,min(len(self.rows)-2,bisect_right(self.times,seconds)-1))
        a,b=self.rows[i:i+2]
        f=(seconds-a[0])/max(b[0]-a[0],1e-9)
        return CarState(x=a[1]+(b[1]-a[1])*f,y=a[2]+(b[2]-a[2])*f,
            heading=a[3]+((b[3]-a[3]+pi)%(2*pi)-pi)*f,steering=a[4]+(b[4]-a[4])*f)

    def delta(self,elapsed,distance):
        if distance<0 or distance>self.progress[-1]: return None
        i=max(0,min(len(self.rows)-2,bisect_right(self.progress,distance)-1))
        a,b=self.rows[i:i+2]
        f=(distance-self.progress[i])/max(self.progress[i+1]-self.progress[i],1e-9)
        return elapsed-(a[0]+(b[0]-a[0])*f)


class Session:
    def __init__(self,car,track,mode,save):
        self.car_id,self.track_id,self.mode,self.save=car,track,mode,save
        self.sim=Simulation(CARS[car],TRACKS[track])
        self.previous=replace(self.sim.state)
        self.countdown=CLIENT.countdown if mode=='Time Trial' else 0.
        self.finished=False
        self.new_best=False
        self.samples=[self.sample(0.)]
        self.ghost=Ghost(save.record(car,track)) if save.record(car,track) else None

    def sample(self,time):
        s=self.sim.state
        return [time,s.x,s.y,s.heading,s.steering,self.sim.lap.distance]

    def step(self,action):
        if self.finished: return
        if self.countdown>0:
            self.countdown=max(0.,self.countdown-PHYSICS.dt)
            if self.countdown<1e-9: self.countdown=0.
            return
        lap=self.sim.lap
        old_elapsed=lap.elapsed
        self.previous=replace(self.sim.state)
        self.sim.step(action)
        crossed=lap.elapsed<old_elapsed
        if crossed:
            # Interpolate the exact line crossing so ghost starts match lap time.
            fraction=1-lap.elapsed/PHYSICS.dt
            a=self.previous; b=self.sim.state
            x=a.x+(b.x-a.x)*fraction; y=a.y+(b.y-a.y)*fraction
            angle=a.heading+((b.heading-a.heading+pi)%(2*pi)-pi)*fraction
            if lap.completed_this_step and self.mode=='Time Trial':
                seconds=lap.lap_times[-1]
                self.samples.append([seconds,x,y,angle,b.steering,self.sim.track.length])
                if self.save.submit(self.car_id,self.track_id,seconds,self.samples):
                    self.new_best=True
                    self.ghost=Ghost(self.save.record(self.car_id,self.track_id))
                self.finished=len(lap.lap_times)>=CLIENT.trial_laps
            self.samples=[[0.,x,y,angle,b.steering,0.]]
        if self.sim.state.ticks%CLIENT.ghost_stride==0 and len(self.samples)<CLIENT.max_ghost_samples-1:
            self.samples.append(self.sample(lap.elapsed))

    def reset_to_track(self):
        if self.mode=='Time Trial': return False
        s=self.sim.state
        point,heading,index=self.sim.track.at(s.progress)
        self.sim.state=CarState(x=float(point[0]),y=float(point[1]),heading=heading,index=index,progress=s.progress)
        self.sim.lap=LapState(previous_progress=s.progress,valid=False,invalid_reason='Practice reset')
        self.previous=replace(self.sim.state)
        self.samples=[self.sample(0.)]
        return True
