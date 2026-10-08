"""Three-circle hull against the closed road corridor, after every substep."""
from math import cos, sin
import numpy as np
from ..config import PHYSICS as P, TRACK
from ..cars import CarSpec
from ..tracks import Track
from .state import CarState
from .physics import clamp


def resolve_walls(state: CarState, car: CarSpec, track: Track) -> None:
    ch, sh = cos(state.heading), sin(state.heading)
    limit = track.spec.width/2 + TRACK.runoff-car.hull_radius
    if abs(state.offset)+car.hull_offset < limit:
        return
    arms = np.array((-car.hull_offset,0.,car.hull_offset))
    points = np.column_stack((state.x+ch*arms,state.y+sh*arms))
    _, offsets, _ = track.nearest_many(points,state.index)
    if np.all(np.abs(offsets) <= limit):
        return
    for _ in range(P.contact_iterations):
        corrected = False
        for arm in (-car.hull_offset, 0., car.hull_offset):
            index, offset, _ = track.nearest(state.x+ch*arm, state.y+sh*arm, state.index)
            if abs(offset) <= limit:
                continue
            corrected = True
            sign = 1 if offset > 0 else -1
            tangent = track.tangent[index]
            nx, ny = -tangent[1]*sign, tangent[0]*sign
            penetration = abs(offset)-limit
            state.x -= nx*penetration
            state.y -= ny*penetration
            wx, wy = state.vx*ch-state.vy*sh, state.vx*sh+state.vy*ch
            normal_speed = wx*nx+wy*ny
            state.wall_contact = True
            state.impact_speed = max(state.impact_speed,normal_speed)
            if normal_speed > 0:
                impulse = (1+P.restitution)*normal_speed
                wx -= nx*impulse
                wy -= ny*impulse
                tangent_speed = wx*tangent[0]+wy*tangent[1]
                friction = min(abs(tangent_speed), P.wall_friction*impulse)
                friction *= 1 if tangent_speed > 0 else -1
                wx -= tangent[0]*friction
                wy -= tangent[1]*friction
                state.vx, state.vy = wx*ch+wy*sh, -wx*sh+wy*ch
                torque = -arm*(ch*ny-sh*nx)*impulse*car.mass/car.inertia
                state.yaw_rate += clamp(torque,-P.max_yaw_kick,P.max_yaw_kick)
        if not corrected:
            break
