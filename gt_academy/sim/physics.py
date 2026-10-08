"""Grippy arcade asphalt handling, progressively released into gravel tire dynamics."""
from math import atan, atan2, cos, sin, sqrt, tan, copysign, hypot, pi, exp
from ..cars import CarSpec
from ..config import PHYSICS as P
from .state import CarState


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def approach(value: float, target: float, amount: float) -> float:
    return value + clamp(target-value, -amount, amount)


def tire_force(slip: float, load: float, grip: float, stiffness: float,
               longitudinal: float = 0.0) -> float:
    """Smooth peak and gentle post-peak falloff, limited by the friction circle."""
    peak = max(grip*load, 1e-9)
    b_slip = stiffness / (P.tire_shape*grip) * slip
    pure = -peak*sin(P.tire_shape*atan(b_slip-P.tire_curvature*(b_slip-atan(b_slip))))
    budget = sqrt(max(0., 1-(longitudinal/peak)**2))
    return pure*budget


def integrate(state: CarState, car: CarSpec, action: tuple[float,float], dt: float,
              grip_front: float = 1., grip_rear: float = 1., offroad: float = 0.) -> None:
    steer, pedal = action
    lock = car.steer_lock / (1+(abs(state.vx)/P.steer_speed_scale)**2)
    target = steer*lock
    state.steering = approach(state.steering, target,
                             min(P.steer_rate*dt, abs(target-state.steering)*P.steer_response*dt))
    state.throttle = approach(state.throttle, max(0.,pedal), P.throttle_slew*dt)
    state.brake = approach(state.brake, max(0.,-pedal), P.brake_slew*dt)
    weight = car.mass*P.gravity
    transfer = clamp(car.mass*state.longitudinal_acceleration*car.cg_height/car.wheelbase,
                     -weight*P.max_load_transfer, weight*P.max_load_transfer)
    front_load = weight*car.front_weight-transfer
    rear_load = weight-front_load
    mu_front, mu_rear = car.grip_front*grip_front, car.grip_rear*grip_rear
    brake_force = state.brake*car.brake_g*weight
    drive = P.acceleration_gain*state.throttle*min(car.mass*car.launch_acceleration,
                              car.power_kw*1000/max(abs(state.vx), P.power_speed_floor))
    # Shared arcade traction distributes propulsion across available road grip.
    # On gravel, the rear-driven tire model retains a small lateral reserve.
    loose = offroad*offroad
    drive_limit = (1-loose)*min(mu_front,mu_rear)*weight + loose*mu_rear*rear_load*(P.drive_grip_fraction-P.offroad_drive_reserve)
    drive = min(drive,drive_limit)
    direction = copysign(1.,state.vx) if abs(state.vx) > P.rest_speed else 1.
    fx_front = -direction*min(brake_force*P.brake_bias, mu_front*front_load)
    fx_rear = clamp(drive-direction*brake_force*(1-P.brake_bias), -mu_rear*rear_load, mu_rear*rear_load)
    speed = max(abs(state.vx), P.slip_speed_floor)
    state.slip_front = atan2(state.vy+car.front_arm*state.yaw_rate, speed)-state.steering*direction
    state.slip_rear = atan2(state.vy-car.rear_arm*state.yaw_rate, speed)
    fy_front = tire_force(state.slip_front, front_load, mu_front, P.front_stiffness, fx_front)
    fy_rear = tire_force(state.slip_rear, rear_load, mu_rear, P.rear_stiffness, fx_rear)
    ca, sa = cos(state.steering), sin(state.steering)
    resist = P.acceleration_gain*(car.drag*state.vx*abs(state.vx) + P.rolling*weight*clamp(state.vx, -1, 1))
    resist += offroad*P.grass_drag*car.mass*state.vx
    ax = (fx_front*ca-fy_front*sa+fx_rear-resist)/car.mass
    ay = (fy_front*ca+fx_front*sa+fy_rear)/car.mass
    angular = (car.front_arm*(fy_front*ca+fx_front*sa)-car.rear_arm*fy_rear)/car.inertia
    blend = clamp((abs(state.vx)-P.kinetic_blend_start)/(P.kinetic_blend_end-P.kinetic_blend_start), 0, 1)
    blend = blend*blend*(3-2*blend)
    old_vx = state.vx
    old_yaw, old_vy = state.yaw_rate, state.vy
    # Asphalt uses shared arcade traction: throttle does not consume steering
    # authority. Beyond the grip limit the turn widens instead of snapping loose.
    arcade_ax = (drive-brake_force*direction-resist)/car.mass
    state.vx += ((1-loose)*arcade_ax+loose*(ax+state.vy*state.yaw_rate))*dt
    if state.brake > state.throttle and old_vx >= 0 and state.vx < 0:
        state.vx = 0.
    dynamic_vy = state.vy + (ay-old_vx*state.yaw_rate)*dt
    dynamic_yaw = state.yaw_rate + angular*dt
    kinetic_yaw = state.vx*tan(state.steering)/car.wheelbase
    kinetic_vy = kinetic_yaw*car.rear_arm
    state.vy = blend*dynamic_vy + (1-blend)*kinetic_vy
    state.yaw_rate = blend*dynamic_yaw + (1-blend)*kinetic_yaw
    # Arcade turning authority is independent of the realistic gravel tire
    # budget. The old road cap forced huge turn radii even at full steering.
    cornering_gain = 1+(P.arcade_cornering_gain-1)*(1-loose)
    yaw_limit = cornering_gain*(mu_front+mu_rear)*.5*P.gravity/max(abs(state.vx),P.slip_speed_floor)
    desired_yaw = clamp(kinetic_yaw,-yaw_limit,yaw_limit)
    # Exponential response is stable at every substep. Gravel progressively
    # releases the assistance, retaining the tire model's recoverable slides.
    arcade_yaw = old_yaw+(desired_yaw-old_yaw)*(1-exp(-P.arcade_yaw_response*dt))
    state.yaw_rate = loose*state.yaw_rate+(1-loose)*arcade_yaw
    arcade_vy = old_vy+(car.rear_arm*state.yaw_rate-old_vy)*(1-exp(-P.arcade_lateral_response*dt))
    state.vy = loose*state.vy+(1-loose)*arcade_vy
    if loose == 0:
        state.yaw_rate = clamp(state.yaw_rate,-yaw_limit,yaw_limit)
    if hypot(state.vx,state.vy) < P.rest_speed and state.throttle == 0:
        state.vx = state.vy = state.yaw_rate = 0.
    state.heading = (state.heading+state.yaw_rate*dt+pi) % (2*pi)-pi
    ch, sh = cos(state.heading), sin(state.heading)
    state.x += (state.vx*ch-state.vy*sh)*dt
    state.y += (state.vx*sh+state.vy*ch)*dt
    state.force_front, state.force_rear = fy_front, fy_rear
    state.longitudinal_acceleration = (1-loose)*arcade_ax+loose*ax
    state.lateral_acceleration = (1-loose)*state.vx*state.yaw_rate+loose*ay
