"""Gymnasium interface over the same simulation used by the human viewer."""
import math
import numpy as np
import gymnasium as gym
from gymnasium import spaces
from ..cars import CARS
from ..tracks import TRACKS
from ..config import ENVIRONMENT as E, PHYSICS as P, TRACK
from ..sim import Simulation, observation, OBSERVATION_NAMES
from ..sim.state import LapState
from .reward import ProgressCredit, driving_reward


class RacingEnv(gym.Env):
    metadata = {'render_modes': []}

    def __init__(self, car_id: int = 0, track_id: int = 0, *, training: bool = True):
        super().__init__()
        self.car_id,self.track_id,self.training = car_id,track_id,training
        self.sim = Simulation(CARS[car_id],TRACKS[track_id])
        self.action_space = spaces.Box(-1.,1.,shape=(2,),dtype=np.float32)
        self.observation_space = spaces.Box(-1.,1.,shape=(len(OBSERVATION_NAMES),),dtype=np.float32)
        self.reference_time = self.sim.track.length/E.reference_speed
        self.time_limit = self.reference_time*E.time_limit_multiplier
        self._done = False

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self.sim.reset()
        s,t = self.sim.state,self.sim.track
        random_start = self.training and not (options or {}).get('grid',False)
        if random_start:
            distance = 0. if self.np_random.random()<E.grid_start_probability else self.np_random.uniform(0,t.length)
            p,heading,index = t.at(distance)
            offset = self.np_random.uniform(-E.start_offset,E.start_offset)
            p += t.normal[index]*offset
            s.x,s.y = float(p[0]),float(p[1])
            s.heading = heading+self.np_random.uniform(-E.start_heading,E.start_heading)
            s.vx = float(self.np_random.uniform(0,E.start_speed))
            s.index,s.offset,s.progress = t.nearest(s.x,s.y,index)
            next_gate = int(np.searchsorted(t.gates,s.progress+1e-6,side='right')) % TRACK.gates
            self.sim.lap = LapState(previous_progress=s.progress,previous_offset=s.offset,next_gate=next_gate)
            self.sim.surfaces()
        elif not self.training:
            variant=int((options or {}).get('evaluation_variant',0))%len(E.evaluation_starts)
            offset,angle=E.evaluation_starts[variant]
            p,heading,index=t.at(0.)
            p+=t.normal[index]*offset
            s.x,s.y=float(p[0]),float(p[1]); s.heading=heading+angle
            s.index,s.offset,s.progress=t.nearest(s.x,s.y,index)
            self.sim.lap=LapState(previous_progress=s.progress,previous_offset=s.offset)
            self.sim.surfaces()
        self.credit = ProgressCredit()
        self.elapsed = self.offroad_time = self.stalled_time = 0.
        self.last_action = np.zeros(2,dtype=np.float32)
        self.episode_reward = 0.
        self.environment_steps = 0
        self._done = False
        return observation(s,self.sim.car,t),self._info('')

    def _info(self, reason: str) -> dict:
        return {'reason':reason,'lap_times':list(self.sim.lap.lap_times),
                'lap_completed':self.sim.lap.completed_this_step,
                'progress_m':self.credit.high_water,'elapsed':self.elapsed,
                'lap_valid':self.sim.lap.valid,'car_id':self.car_id,'track_id':self.track_id}

    def step(self, action):
        if self._done:
            raise RuntimeError('Call reset() after an episode ends')
        action = np.asarray(action,dtype=np.float32)
        if action.shape != (2,) or not np.isfinite(action).all():
            raise ValueError('Expected two finite action values')
        action = np.clip(action,-1,1)
        reward = 0.
        reason = ''
        completed = False
        for substep in range(E.frame_skip):
            before = self.sim.state.progress
            s = self.sim.step(action)
            t = self.sim.track
            delta = (s.progress-before+t.length/2)%t.length-t.length/2
            offroad = sum(not on for on in s.wheel_asphalt)/4
            on_course = abs(s.offset)<=t.spec.width/2+TRACK.kerb_width
            illegal = abs(delta)>TRACK.max_progress_step or self.sim.lap.invalid_reason in ('Missed gate','Skipped distance / teleport')
            progress = self.credit.advance(delta,on_course and not illegal)
            self.elapsed += P.dt
            self.offroad_time = self.offroad_time+P.dt if not on_course else 0.
            self.stalled_time = 0. if progress>.01 else self.stalled_time+P.dt
            lap_time = self.sim.lap.lap_times[-1] if self.sim.lap.completed_this_step else None
            completed |= self.sim.lap.completed_this_step
            jerk = float(np.sum((action-self.last_action)**2)) if substep==0 else 0.
            reward += driving_reward(progress,P.dt,offroad,s.impact_speed,jerk,lap_time,self.reference_time)
            if illegal:
                reason = 'invalid_route'
            elif s.impact_speed>=E.serious_impact:
                reason = 'wall_impact'
            elif self.offroad_time>=E.offroad_timeout:
                reason = 'offroad'
            elif self.credit.distance<self.credit.high_water-E.backward_limit:
                reason = 'backwards'
            elif self.stalled_time>=E.stalled_timeout:
                reason = 'no_progress'
            elif len(self.sim.lap.lap_times)>=E.max_laps:
                reason = 'lap_complete'
            elif self.elapsed>=self.time_limit:
                reason = 'time_limit'
            if reason:
                break
        self.last_action = action.copy()
        self.environment_steps += 1
        self.episode_reward += reward
        self._done = bool(reason)
        info = self._info(reason)
        info['lap_completed'] = completed
        if self._done:
            info['episode'] = {'r':self.episode_reward,'l':self.environment_steps,
                               't':self.elapsed}
        return observation(s,self.sim.car,t),float(reward),bool(reason and reason!='time_limit'),reason=='time_limit',info
