"""Regressions for arcade handling and smooth presentation."""
from dataclasses import asdict
from math import atan2, pi
import os
import pytest
from gt_academy.cars import CARS
from gt_academy.config import PHYSICS as P, VIEWER as V
from gt_academy.sim.physics import integrate, approach
from gt_academy.sim.state import CarState
from tools.validate_physics import straight_metrics


@pytest.mark.parametrize('car,baseline',list(zip(CARS,(4.783,3.867,5.083,4.433,4.1))),ids=[c.name for c in CARS])
def test_at_least_25_percent_shorter_launch(car,baseline):
    assert straight_metrics(car)['zero_to_100_s'] <= baseline*.75


@pytest.mark.parametrize('car',CARS,ids=lambda c:c.name)
@pytest.mark.parametrize('speed',(15.,35.,60.))
def test_asphalt_slalom_and_release_do_not_spin(car,speed):
    state=CarState(vx=speed)
    for tick in range(360):
        steer=1. if (tick//30)%2==0 else -1.
        pedal=1. if tick<180 else -1.
        for _ in range(P.substeps):
            integrate(state,car,(steer,pedal),P.dt/P.substeps)
        # Rear-axle slip excludes the body's normal kinematic turning motion.
        assert abs(atan2(state.vy-car.rear_arm*state.yaw_rate,max(state.vx,2))) < .2
        assert abs(state.yaw_rate)*abs(state.vx) <= P.arcade_cornering_gain*(car.grip_front+car.grip_rear)*.5*P.gravity+.01
    state=CarState(vx=speed,steering=.1,yaw_rate=.4,vy=1.)
    for _ in range(30*P.substeps):
        integrate(state,car,(0,0),P.dt/P.substeps)
    assert abs(state.yaw_rate)<.001
    assert abs(state.vy)<.01


@pytest.mark.parametrize('car',CARS,ids=lambda c:c.name)
def test_keyboard_turn_has_meaningful_response_in_100ms(car):
    state=CarState(vx=20.)
    keyboard=0.
    for _ in range(6):
        keyboard=approach(keyboard,1,V.keyboard_rate*P.dt)
        for _ in range(P.substeps):
            integrate(state,car,(keyboard,1),P.dt/P.substeps)
    assert state.yaw_rate > .45


@pytest.mark.parametrize('car',CARS,ids=lambda c:c.name)
@pytest.mark.parametrize('speed',(20.,35.,55.))
def test_full_steering_makes_substantially_tighter_turns(car,speed):
    # Constant-speed steering calibration: road cornering, without track walls.
    state=CarState(vx=speed)
    for _ in range(60*P.substeps):
        state.vx=speed
        integrate(state,car,(1,0),P.dt/P.substeps)
    old_radius=speed**2/((car.grip_front+car.grip_rear)*.5*P.gravity)
    radius=state.vx/abs(state.yaw_rate)
    assert radius < old_radius*.42


def test_gravel_releases_grip_but_edge_grazing_does_not():
    states=[]
    for offroad in (0.,.04,1.):
        state=CarState(vx=25.,vy=4.,yaw_rate=.8)
        grip=1+(P.grass_grip-1)*offroad
        for _ in range(30*P.substeps):
            integrate(state,CARS[4],(.7,1),P.dt/P.substeps,grip,grip,offroad)
        states.append(state)
    assert abs(states[0].vy-states[1].vy)<.2
    assert abs(states[2].vy)>abs(states[0].vy)*2


def test_interpolation_wraps_heading_and_never_mutates_simulation():
    from gt_academy.game.debug_viewer import interpolate_state
    previous=CarState(x=10.,heading=pi-.1)
    current=CarState(x=12.,heading=-pi+.1)
    before=(asdict(previous),asdict(current))
    for alpha in (0.,.25,.5,.75,1.):
        rendered=interpolate_state(previous,current,alpha)
        assert rendered.x==pytest.approx(10+2*alpha)
        assert rendered.heading==pytest.approx(pi-.1+.2*alpha)
    assert before==(asdict(previous),asdict(current))


def test_viewer_renders_without_changing_simulation():
    os.environ['SDL_VIDEODRIVER']='dummy'
    os.environ['SDL_AUDIODRIVER']='dummy'
    import pygame
    from gt_academy.game.debug_viewer import DebugViewer
    viewer=DebugViewer()
    try:
        viewer.sim.step((.2,1))
        before=asdict(viewer.sim.state)
        for elapsed in (1/30,1/60,1/120):
            viewer.frame_dt=elapsed
            viewer.draw()
        assert asdict(viewer.sim.state)==before
        assert not viewer.rays and not viewer.forces and not viewer.diagnostics
    finally:
        pygame.quit()
