"""Pure 32-float observation shared by future game policies and training."""
from math import cos, sin, pi
import numpy as np
from ..config import SENSORS as C
from ..cars import CarSpec
from ..tracks import Track
from .state import CarState

RAY_ANGLES = np.deg2rad(np.linspace(-C.spread_degrees,C.spread_degrees,C.rays))
OBSERVATION_NAMES = tuple([f'ray_{i}' for i in range(C.rays)] + [
    'forward_speed','lateral_speed','yaw_rate','steering','throttle','brake',
    'front_slip','rear_slip','lateral_offset','heading_error','left_edge','right_edge',
    'curvature_10m','curvature_20m','curvature_40m','curvature_70m','straight_remaining',
    'front_right_asphalt','front_left_asphalt','rear_right_asphalt','rear_left_asphalt'])
ACTION_NAMES = ('steering','throttle_brake')


def ray_distances(state: CarState, track: Track) -> np.ndarray:
    if abs(state.offset) >= track.spec.width/2:
        return np.zeros(C.rays)
    indices = (np.arange(-C.ray_window,C.ray_window+1)+state.index) % track.count
    starts = np.vstack((track.left[indices],track.right[indices]))
    ends = np.vstack((track.left[(indices+1)%track.count],track.right[(indices+1)%track.count]))
    segments = ends-starts
    q = starts-np.array((state.x,state.y))
    angles = RAY_ANGLES+state.heading
    directions = np.column_stack((np.cos(angles),np.sin(angles)))
    cross = directions[:,0,None]*segments[None,:,1]-directions[:,1,None]*segments[None,:,0]
    safe_cross = np.where(abs(cross)>1e-10,cross,np.nan)
    distance = (q[:,0]*segments[:,1]-q[:,1]*segments[:,0])[None,:]/safe_cross
    fraction = (q[None,:,0]*directions[:,1,None]-q[None,:,1]*directions[:,0,None])/safe_cross
    valid = (distance >= 0) & (fraction >= 0) & (fraction <= 1)
    return np.minimum(np.min(np.where(valid,distance,C.ray_range),axis=1),C.ray_range)


def observation(state: CarState, car: CarSpec, track: Track) -> np.ndarray:
    tangent = track.tangent[state.index]
    heading_error = (state.heading-np.arctan2(tangent[1],tangent[0])+pi)%(2*pi)-pi
    half = track.spec.width/2
    ahead = [track.at(state.progress+d)[2] for d in C.lookahead]
    values = list(ray_distances(state,track)/C.ray_range)
    values += [state.vx/C.speed_scale,state.vy/C.lateral_speed_scale,state.yaw_rate/C.yaw_scale,
               state.steering/car.steer_lock,state.throttle,state.brake,
               state.slip_front/C.slip_scale,state.slip_rear/C.slip_scale,
               state.offset/half,heading_error/pi,(half-state.offset)/track.spec.width,
               (half+state.offset)/track.spec.width]
    values += [track.curvature[i]/C.curvature_scale for i in ahead]
    values += [track.straight[state.index]/C.straight_range]
    values += [1. if on else -1. for on in state.wheel_asphalt]
    return np.clip(np.asarray(values,dtype=np.float32),-1,1)
