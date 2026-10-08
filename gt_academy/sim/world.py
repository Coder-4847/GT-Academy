"""Fixed-step orchestrator. Input is the same two floats for every driver."""
from math import cos, sin, isfinite
import numpy as np
from ..cars import CarSpec
from ..tracks import Track
from ..config import PHYSICS as P, TRACK
from .physics import integrate, clamp
from .state import CarState, LapState
from .laps import update_lap
from .collisions import resolve_walls


class Simulation:
    def __init__(self, car: CarSpec, track: Track):
        self.car, self.track = car, track
        self._wheel_arms = np.array((car.front_arm,car.front_arm,-car.rear_arm,-car.rear_arm))
        self._wheel_sides = np.array((-car.hull_radius,car.hull_radius,-car.hull_radius,car.hull_radius))
        self.reset()

    def reset(self, slot: int = 0) -> CarState:
        p, heading, index = self.track.grid(slot)
        self.state = CarState(x=float(p[0]), y=float(p[1]), heading=heading,index=index)
        self.state.index,self.state.offset,self.state.progress = self.track.nearest(*p,index)
        self.lap = LapState(previous_progress=self.state.progress, previous_offset=self.state.offset,
                            valid=slot == 0, next_gate=1)
        return self.state

    def surfaces(self) -> tuple[float,float,float]:
        s,c,t = self.state,self.car,self.track
        ch,sh = cos(s.heading),sin(s.heading)
        half = t.spec.width/2
        # Distance-to-boundary is Lipschitz inside this non-overlapping road
        # corridor. A conservative hull bound avoids four queries on asphalt.
        reach = max(c.front_arm,c.rear_arm)+c.hull_radius
        if abs(s.offset)+reach < half:
            s.wheel_asphalt = (True,True,True,True)
            s.surface_front = s.surface_rear = 'asphalt'
            return 1.,1.,0.
        arms,sides = self._wheel_arms,self._wheel_sides
        points = np.column_stack((s.x+ch*arms-sh*sides,s.y+sh*arms+ch*sides))
        indices,offsets,_ = t.nearest_many(points,s.index)
        asphalt = np.abs(offsets) <= half
        kerb_side = np.where(offsets>0,t.kerb_left[indices],t.kerb_right[indices])
        kerbs = (np.abs(offsets) <= half+TRACK.kerb_width) & kerb_side
        edge_start = half + np.where(kerb_side,TRACK.kerb_width,0.)
        depth = np.clip((np.abs(offsets)-edge_start)/P.edge_blend_width,0,1)
        blend = depth*depth*(3-2*depth)
        base = np.where(kerb_side & ~asphalt,P.kerb_grip,1.)
        wheel_grips = base+(P.grass_grip-base)*blend
        names=[]
        for a,b in ((0,2),(2,4)):
            names.append('grass' if np.any(~asphalt[a:b] & ~kerbs[a:b]) else ('kerb' if np.any(~asphalt[a:b]) else 'asphalt'))
        s.wheel_asphalt = tuple(bool(value) for value in asphalt)
        s.surface_front,s.surface_rear = names
        offroad = float(np.mean(blend))
        return float(np.mean(wheel_grips[:2])),float(np.mean(wheel_grips[2:])),offroad

    def step(self, action: tuple[float,float]) -> CarState:
        if len(action) != 2 or not all(isfinite(float(value)) for value in action):
            raise ValueError('Action must contain finite steering and throttle/brake values')
        action = (clamp(float(action[0]),-1,1),clamp(float(action[1]),-1,1))
        s = self.state
        s.wall_contact,s.impact_speed = False,0.
        for _ in range(P.substeps):
            front,rear,offroad = self.surfaces()
            integrate(s,self.car,action,P.dt/P.substeps,front,rear,offroad)
            s.index,s.offset,s.progress = self.track.nearest(s.x,s.y,s.index)
            resolve_walls(s,self.car,self.track)
            if s.wall_contact:
                s.index,s.offset,s.progress = self.track.nearest(s.x,s.y,s.index)
        s.index,s.offset,s.progress = self.track.nearest(s.x,s.y,s.index)
        self.surfaces()
        s.ticks += 1
        update_lap(self.lap,self.track,s.progress,s.offset)
        return s
