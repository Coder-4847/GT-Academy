from dataclasses import asdict
import math
import subprocess
import sys
import numpy as np
import pytest
from gt_academy.cars import CARS
from gt_academy.tracks import TRACKS
from gt_academy.config import PHYSICS as P, TRACK
from gt_academy.sim import Simulation, observation, OBSERVATION_NAMES, SIM_VERSION, require_version
from gt_academy.sim.state import CarState, LapState
from gt_academy.sim.laps import update_lap
from gt_academy.sim.physics import tire_force
from gt_academy.sim.sensors import ray_distances
from tools.validate_physics import straight_metrics, skidpad_metrics


@pytest.mark.parametrize('car',CARS,ids=lambda c:c.name)
def test_determinism_and_rest(car):
    a,b=Simulation(car,TRACKS[0]),Simulation(car,TRACKS[0])
    before=(a.state.x,a.state.y,a.state.heading)
    for _ in range(60):
        a.step((0,0))
    assert (a.state.x,a.state.y,a.state.heading)==before
    a.reset()
    for i in range(360):
        action=(math.sin(i/40)*.6,.7 if i<240 else -.8)
        a.step(action); b.step(action)
        assert asdict(a.state)==asdict(b.state)


@pytest.fixture(scope='module')
def calibration():
    return {car.name:straight_metrics(car) for car in CARS}


@pytest.mark.parametrize('car',CARS,ids=lambda c:c.name)
def test_top_speed(car,calibration):
    assert abs(calibration[car.name]['top_kph']/car.top_kph-1)<.03


def test_acceleration_and_braking_order(calibration):
    assert min(calibration,key=lambda name:calibration[name]['zero_to_100_s'])=='Bolt'
    assert min(calibration,key=lambda name:calibration[name]['braking_150_m'])=='Vector'
    assert max(calibration,key=lambda name:calibration[name]['braking_150_m'])=='Comet'


@pytest.mark.parametrize('car',CARS,ids=lambda c:c.name)
def test_skidpad_and_combined_grip(car):
    metrics=skidpad_metrics(car)
    expected=P.arcade_cornering_gain*(car.grip_front+car.grip_rear)/2
    assert .75*expected < metrics['peak_lateral_g'] < 1.15*expected
    # Every car now holds asphalt grip, including the formerly drift-biased Rogue.
    assert metrics['rear_slip_at_peak_deg'] < 2
    load=car.mass*P.gravity/2
    slip=np.linspace(0,1,1000)
    pure=max(abs(tire_force(s,load,car.grip_front,P.front_stiffness)) for s in slip)
    combined=max(abs(tire_force(s,load,car.grip_front,P.front_stiffness,.8*car.grip_front*load)) for s in slip)
    assert pure==pytest.approx(car.grip_front*load,rel=.01)
    assert combined < pure*.61
    assert abs(tire_force(1,load,car.grip_front,P.front_stiffness)) < pure


@pytest.mark.parametrize('track',TRACKS,ids=lambda t:t.spec.name)
def test_tracks_and_local_lookup(track):
    track.validate()
    for i in range(0,track.count,73):
        point=track.center[i]+track.normal[i]*2
        local=track.nearest(*point,(i-3)%track.count)
        global_=track.nearest(*point)
        assert local==pytest.approx(global_,abs=1e-8)
    assert not track.center.flags.writeable


@pytest.mark.parametrize('track',TRACKS,ids=lambda t:t.spec.name)
@pytest.mark.parametrize('side',(-1,1))
def test_wall_cannot_tunnel(track,side):
    car=CARS[3]
    for index in (0,int(np.argmax(abs(track.curvature))),track.count//2):
        sim=Simulation(car,track)
        # Start inside a wall, aimed straight out at the fastest car's top speed.
        point=track.center[index]+side*track.normal[index]*(track.spec.width/2+TRACK.runoff-3)
        sim.state.x,sim.state.y=map(float,point)
        sim.state.index=index
        sim.state.heading=math.atan2(side*track.normal[index,1],side*track.normal[index,0])
        sim.state.vx=car.top_kph/3.6
        contacted=False
        for _ in range(15):
            sim.step((0,1))
            contacted |= sim.state.wall_contact
            for arm in (-car.hull_offset,0,car.hull_offset):
                s=sim.state
                _,offset,_=track.nearest(s.x+math.cos(s.heading)*arm,s.y+math.sin(s.heading)*arm,s.index)
                assert abs(offset)+car.hull_radius <= track.spec.width/2+TRACK.runoff+.025
        assert contacted


def walk_lap(lap,track,direction=1,offset=0):
    steps=math.ceil(track.length/2)
    for i in range(1,steps+1):
        update_lap(lap,track,(direction*i*track.length/steps)%track.length,offset)


def test_lap_gates_and_reverse_and_shortcuts():
    track=TRACKS[0]
    lap=LapState()
    walk_lap(lap,track)
    assert len(lap.lap_times)==1
    assert lap.best==pytest.approx(math.ceil(track.length/2)*P.dt,abs=1e-6)
    reverse=LapState()
    walk_lap(reverse,track,-1)
    assert not reverse.lap_times
    cut=LapState()
    update_lap(cut,track,track.length/2,0)
    walk_lap(cut,track)
    assert not cut.lap_times
    offroad=LapState()
    walk_lap(offroad,track,offset=track.spec.width)
    assert not offroad.lap_times


def test_observation_pure_and_bounded():
    for car in CARS:
        for track in TRACKS:
            sim=Simulation(car,track)
            before=asdict(sim.state)
            first=observation(sim.state,car,track)
            assert first.shape==(len(OBSERVATION_NAMES),)==(32,)
            assert first.dtype==np.float32
            assert np.isfinite(first).all() and np.max(abs(first))<=1
            assert np.array_equal(first,observation(sim.state,car,track))
            assert before==asdict(sim.state)
            assert np.all(ray_distances(sim.state,track)>0)


def test_surfaces_and_action_validation():
    sim=Simulation(CARS[0],TRACKS[0])
    index=100
    point=sim.track.center[index]+sim.track.normal[index]*(sim.track.spec.width/2+3)
    sim.state.x,sim.state.y=map(float,point)
    sim.state.heading=sim.track.at(sim.track.distance[index])[1]
    sim.state.index=index
    sim.state.index,sim.state.offset,sim.state.progress=sim.track.nearest(*point,index)
    front,rear,offroad=sim.surfaces()
    assert front==rear==P.grass_grip
    assert offroad==1
    assert not any(sim.state.wheel_asphalt)
    for bad in ((float('nan'),0),(0,float('inf')),(1,)):
        with pytest.raises(ValueError):
            sim.step(bad)


def test_hash_and_headless_import():
    assert len(SIM_VERSION)==64
    require_version(SIM_VERSION)
    with pytest.raises(ValueError,match='Retraining required'):
        require_version('old-model')
    result=subprocess.run([sys.executable,'-c',
        'import sys; import gt_academy.sim; assert "pygame" not in sys.modules'],capture_output=True,text=True)
    assert result.returncode==0,result.stderr


def test_actuator_limits_and_batch_queries():
    sim=Simulation(CARS[0],TRACKS[0])
    sim.step((1,1))
    assert abs(sim.state.steering) <= P.steer_rate*P.dt+1e-12
    assert sim.state.throttle <= P.throttle_slew*P.dt+1e-12
    sim.step((-1,-1))
    assert sim.state.brake <= P.brake_slew*P.dt+1e-12
    for track in TRACKS:
        for hint in (0,track.count-1,track.count//2):
            points=track.center[(np.arange(4)+hint)%track.count]+track.normal[hint]*3
            indices,offsets,progress=track.nearest_many(points,hint)
            for k,point in enumerate(points):
                assert track.nearest(*point,hint)==pytest.approx((indices[k],offsets[k],progress[k]))


def test_ray_hits_match_full_edge_search():
    from gt_academy.sim.sensors import RAY_ANGLES
    from gt_academy.config import SENSORS
    for track in TRACKS:
        for index in (0,int(np.argmax(abs(track.curvature))),track.count//3):
            point,heading,_=track.at(track.distance[index])
            state=CarState(x=float(point[0]),y=float(point[1]),heading=heading+.2,index=index)
            actual=ray_distances(state,track)
            starts=np.vstack((track.left,track.right))
            ends=np.vstack((np.roll(track.left,-1,axis=0),np.roll(track.right,-1,axis=0)))
            segment=ends-starts
            q=starts-point
            for angle,hit in zip(RAY_ANGLES+state.heading,actual):
                direction=np.array((math.cos(angle),math.sin(angle)))
                cross=direction[0]*segment[:,1]-direction[1]*segment[:,0]
                with np.errstate(divide='ignore',invalid='ignore'):
                    distance=(q[:,0]*segment[:,1]-q[:,1]*segment[:,0])/cross
                    along=(q[:,0]*direction[1]-q[:,1]*direction[0])/cross
                valid=(distance>=0)&(along>=0)&(along<=1)
                expected=min(SENSORS.ray_range,np.min(distance[valid]))
                assert hit==pytest.approx(expected,abs=1e-5)


def test_complete_lap_through_actual_physics():
    # A slow geometric test driver exercises physics + queries + ordered gates.
    # It is a test fixture, never a game opponent or a substitute for RL.
    sim=Simulation(CARS[0],TRACKS[0])
    for _ in range(10000):
        s=sim.state
        point,_,_=sim.track.at(s.progress+12)
        error=(math.atan2(point[1]-s.y,point[0]-s.x)-s.heading+math.pi)%(2*math.pi)-math.pi
        steering=math.atan(2*sim.car.wheelbase*math.sin(error)/12)
        lock=sim.car.steer_lock/(1+(abs(s.vx)/P.steer_speed_scale)**2)
        pedal=max(-1,min(1,(16-s.vx)*.8))
        sim.step((steering/lock,pedal))
        assert not s.wall_contact
        assert sim.lap.valid
        if sim.lap.completed_this_step:
            break
    assert len(sim.lap.lap_times)==1
