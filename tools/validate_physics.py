"""Reproducible straight-line and skidpad bug checks, without track walls."""
import json
import argparse
from math import pi
from pathlib import Path
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gt_academy.cars import CARS, CarSpec
from gt_academy.config import PHYSICS as P
from gt_academy.sim.state import CarState
from gt_academy.sim.physics import integrate, clamp


def free_step(state: CarState, car: CarSpec, action: tuple[float,float]) -> None:
    for _ in range(P.substeps):
        integrate(state,car,action,P.dt/P.substeps)


def straight_metrics(car: CarSpec) -> dict:
    state = CarState()
    zero_to_hundred = None
    for tick in range(120*60):
        free_step(state,car,(0.,1.))
        if zero_to_hundred is None and state.vx >= 100/3.6:
            zero_to_hundred = (tick+1)*P.dt
    top = state.vx*3.6
    state = CarState(vx=150/3.6)
    for tick in range(20*60):
        free_step(state,car,(0.,-1.))
        if state.vx == 0:
            break
    return {'car':car.name,'top_kph':round(top,3),'target_kph':car.top_kph,
            'zero_to_100_s':round(zero_to_hundred,3),'braking_150_m':round(state.x,3)}


def skidpad_metrics(car: CarSpec) -> dict:
    # Sweep steer slowly at 20 m/s. A speed controller supplies only enough
    # throttle to sustain speed; there are no tire-force shortcuts in this test.
    peak,front,rear = 0.,0.,0.
    state = CarState(vx=20.)
    for tick in range(25*60):
        steering = min(1.,tick/(20*60))
        pedal = clamp((20-state.vx)*0.8,-1,1)
        free_step(state,car,(steering,pedal))
        if tick > 120:
            if abs(state.lateral_acceleration)/P.gravity > peak:
                peak = abs(state.lateral_acceleration)/P.gravity
                front,rear = abs(state.slip_front),abs(state.slip_rear)
    return {'peak_lateral_g':round(peak,3),'front_slip_at_peak_deg':round(front*180/pi,2),
            'rear_slip_at_peak_deg':round(rear*180/pi,2)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args = parser.parse_args()
    results = [dict(straight_metrics(car),**skidpad_metrics(car)) for car in CARS]
    print('Physics calibration bug check; no training or hardware claims.')
    print(json.dumps(results,indent=2))
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')


if __name__ == '__main__':
    main()
