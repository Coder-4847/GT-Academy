"""Short integration bug checks. These do not test learning quality or throughput."""
from dataclasses import asdict
import json
import math
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4
import numpy as np
import pytest
from gt_academy.rl.runtime import configure_environment,configure_torch
configure_environment()
configure_torch()
from stable_baselines3 import PPO
from stable_baselines3.common.env_checker import check_env
from stable_baselines3.common.vec_env import DummyVecEnv,VecNormalize
from gt_academy.cars import CARS
from gt_academy.tracks import TRACKS
from gt_academy.config import PHYSICS as P,VIEWER,ENVIRONMENT
from gt_academy.sim import SIM_VERSION
from gt_academy.sim.physics import approach
from gt_academy.rl.env import RacingEnv
from gt_academy.rl.reward import ProgressCredit
from gt_academy.rl.storage import (save_checkpoint,validate_checkpoint,latest_checkpoint,
    run_path,atomic_json,read_json,writer_lock,ensure_freeze)
from gt_academy.rl.policy import Driver
from gt_academy.rl.training import TrainingCallback,StopRequest,parser as train_parser
from gt_academy.rl.launcher import parser as launch_parser,launch
from tools.validate_physics import free_step
from gt_academy.sim.state import CarState


@pytest.fixture(scope='module')
def scratch():
    # Kept as reviewable artifacts: no dependency on sandbox-restricted temp cleanup.
    path=Path('artifacts')/('pytest_rl_'+uuid4().hex[:8])
    path.mkdir(parents=True)
    return path


def test_gym_api_and_seeded_resets():
    check_env(RacingEnv())
    a,b=RacingEnv(),RacingEnv()
    for seed in (1,10,42):
        x,_=a.reset(seed=seed); y,_=b.reset(seed=seed)
        assert np.array_equal(x,y)
        for _ in range(30):
            result_a=a.step(np.array((.15,.6),np.float32))
            result_b=b.step(np.array((.15,.6),np.float32))
            assert np.array_equal(result_a[0],result_b[0])
            assert result_a[1:]==result_b[1:]
            if result_a[2] or result_a[3]: break


@pytest.mark.parametrize('car',range(5))
@pytest.mark.parametrize('track',range(5))
def test_every_training_pair(car,track):
    env=RacingEnv(car,track)
    obs,_=env.reset(seed=car*5+track)
    for _ in range(4):
        obs,reward,terminated,truncated,info=env.step(np.array((0.,.2),np.float32))
        assert env.observation_space.contains(obs)
        assert math.isfinite(reward)
        if terminated or truncated: break


def test_progress_credit_cannot_be_farmed():
    credit=ProgressCredit()
    assert credit.advance(5,True)==5
    assert credit.advance(-3,True)==0
    assert credit.advance(3,True)==0
    assert credit.advance(2,False)==0
    assert credit.advance(-2,True)==0
    assert credit.advance(2,True)==0
    assert credit.advance(1,True)==1


def test_termination_and_time_truncation():
    env=RacingEnv(training=False)
    env.reset()
    for _ in range(math.ceil(ENVIRONMENT.stalled_timeout/(P.dt*ENVIRONMENT.frame_skip))+2):
        _,_,terminated,truncated,info=env.step((0,0))
        if terminated or truncated: break
    assert terminated and not truncated and info['reason']=='no_progress'
    with pytest.raises(RuntimeError): env.step((0,1))
    env.reset(); env.elapsed=env.time_limit
    _,_,terminated,truncated,info=env.step((0,1))
    assert truncated and not terminated and info['reason']=='time_limit'
    env.reset(); env.credit.high_water=100
    _,_,terminated,_,info=env.step((0,0))
    assert terminated and info['reason']=='backwards'


def test_quicker_keyboard_response():
    state=CarState(vx=20.)
    car=CARS[0]; keyboard=0.
    for _ in range(9):
        keyboard=approach(keyboard,1.,VIEWER.keyboard_rate*P.dt)
        free_step(state,car,(keyboard,.2))
    lock=car.steer_lock/(1+(state.vx/P.steer_speed_scale)**2)
    assert state.steering>lock*.5  # meaningful steering within 150 ms
    assert abs(state.yaw_rate)>.15


def test_grazing_edge_retains_grip():
    env=RacingEnv()
    env.reset()
    sim=env.sim; t=sim.track
    index=int(np.argmin(abs(t.curvature)))
    point,heading,_=t.at(t.distance[index])
    point+=t.normal[index]*(t.spec.width/2-sim.car.hull_radius+.05)
    s=sim.state; s.x,s.y=map(float,point); s.heading=heading
    s.index,s.offset,s.progress=t.nearest(s.x,s.y,index)
    front,rear,drag=sim.surfaces()
    assert front>.94 and rear>.94 and drag<.05
    assert not all(s.wheel_asphalt)


@pytest.fixture(scope='module')
def trained_bundle(scratch):
    base=DummyVecEnv([lambda:RacingEnv() for _ in range(2)])
    normalizer=VecNormalize(base)
    model=PPO('MlpPolicy',normalizer,n_steps=8,batch_size=16,n_epochs=1,
              policy_kwargs={'net_arch':[32,32]},seed=7,device='cpu')
    model.learn(total_timesteps=32)  # tiny PPO update, strictly a serialization bug check
    run=run_path(scratch/'bundles',0,0)
    checkpoint=save_checkpoint(model,normalizer,run,{'car_id':0,'track_id':0,'training_seconds':1})
    yield model,normalizer,run,checkpoint
    normalizer.close()


def test_checkpoint_normalization_and_policy_parity(trained_bundle):
    model,normalizer,run,checkpoint=trained_bundle
    metadata=validate_checkpoint(checkpoint,0,0)
    assert metadata['steps']==32
    raw,_=RacingEnv(training=False).reset()
    expected,_=model.predict(normalizer.normalize_obs(raw.reshape(1,-1)),deterministic=True)
    driver=Driver(checkpoint,0,0)
    assert np.allclose(driver.action(raw),expected[0],atol=1e-7)
    before=driver.normalizer.obs_rms.count
    driver.action(raw)
    assert driver.normalizer.obs_rms.count==before
    driver.close()
    with pytest.raises(ValueError,match='car_id'): Driver(checkpoint,1,0)
    assert latest_checkpoint(run)==checkpoint


def test_resume_optimizer_steps_and_normalizer(trained_bundle,scratch):
    _,_,_,checkpoint=trained_bundle
    base=DummyVecEnv([lambda:RacingEnv() for _ in range(2)])
    norm=VecNormalize.load(checkpoint/'vecnormalize.pkl',base)
    count=norm.obs_rms.count
    model=PPO.load(checkpoint/'model.zip',env=norm,device='cpu')
    assert model.num_timesteps==32 and model.policy.optimizer.state
    model.learn(total_timesteps=16,reset_num_timesteps=False)
    assert model.num_timesteps==48 and norm.obs_rms.count>count
    norm.close()


def test_corruption_fallback_and_version_rejection(trained_bundle,scratch):
    model,norm,_,_=trained_bundle
    run=scratch/'corruption'
    good=save_checkpoint(model,norm,run,{'car_id':0,'track_id':0})
    bad=save_checkpoint(model,norm,run,{'car_id':0,'track_id':0})
    (bad/'vecnormalize.pkl').write_bytes(b'corrupt')
    assert latest_checkpoint(run)==good
    (run/'checkpoints'/'.partial-abandoned').mkdir()
    assert latest_checkpoint(run)==good
    data=read_json(good/'metadata.json'); data['sim_version']='old'
    atomic_json(good/'metadata.json',data)
    with pytest.raises(ValueError,match='Simulation mismatch'): validate_checkpoint(good)


def test_writer_lock_and_physics_lock(scratch):
    run=scratch/'locking'
    with writer_lock(run):
        with pytest.raises(OSError):
            with writer_lock(run): pass
    with writer_lock(run): pass
    ensure_freeze(run)
    assert read_json(run/'physics_lock.json')['sim_version']==SIM_VERSION
    atomic_json(run/'physics_lock.json',{'sim_version':'different'})
    with pytest.raises(ValueError,match='Simulation mismatch'): ensure_freeze(run)


def test_stop_request_is_shared_by_signal_and_file(scratch):
    path=scratch/'STOP'
    stop=StopRequest(path)
    assert not stop()
    stop.signal(); assert stop()
    stop=StopRequest(path)
    path.write_text('stop',encoding='utf-8')
    assert stop()


def test_launcher_restarts_and_obeys_concurrency(monkeypatch,scratch):
    import gt_academy.rl.launcher as module
    active=[0]; peak=[0]; calls=[]; attempts={}
    class FakeProcess:
        def __init__(self,command,**kwargs):
            self.car=int(command[command.index('--car-id')+1])
            attempts[self.car]=attempts.get(self.car,0)+1
            self.code=1 if self.car==0 and attempts[self.car]==1 else 0
            self.pid=1000+len(calls); self.finished=False
            calls.append(command); active[0]+=1; peak[0]=max(peak[0],active[0])
        def poll(self):
            if not self.finished: active[0]-=1; self.finished=True
            return self.code
        def wait(self,timeout=None): return self.poll()
        def terminate(self): self.poll()
    monkeypatch.setattr(module.subprocess,'Popen',FakeProcess)
    monkeypatch.setattr(module.time,'sleep',lambda _:None)
    args=launch_parser().parse_args(['--root',str(scratch/'launcher'),'--cars','1,2,3','--tracks','1','--max-concurrent','2','--experiment'])
    result=launch(args)
    assert peak[0]<=2 and len(calls)==4
    assert all(job['status']=='completed' for job in result['jobs'])
    assert result['jobs'][0]['restarts']==1
    assert all('--resume' in command for command in calls)


def test_monitor_accepts_windows_redirector_pid(scratch):
    from tools.monitor import snapshot
    root=scratch/'monitor'
    atomic_json(root/'launcher.json',{'jobs':[{'car_id':0,'track_id':0,'pid':10,
                                             'worker_token':'current','status':'running'}]})
    atomic_json(run_path(root,0,0)/'status.json',{'pid':20,'worker_token':'current','status':'training',
                'updated_at':time.time(),'steps':100,'steps_per_second':300})
    line=next(line for line in snapshot(root,1000000).splitlines() if line.startswith('Sunrise Oval / Atlas'))
    assert line.endswith('training') and 'starting' not in line


def test_evaluation_preserves_training_rng(monkeypatch,trained_bundle):
    import random
    import torch
    import gt_academy.rl.training as training
    model,normalizer,run,checkpoint=trained_bundle
    args=train_parser().parse_args(['--car-id','0','--track-id','0'])
    callback=TrainingCallback(args,run,StopRequest(None),{})
    callback.init_callback(model)
    def fake_evaluation(*args,**kwargs):
        random.random(); np.random.random(); torch.rand(3)
        return {'best_lap':None,'mean_lap':None,'completion_rate':0.,'episodes':1,'completed_laps':0,'failures':{'no_progress':1}}
    monkeypatch.setattr(training,'evaluate',fake_evaluation)
    before=(random.getstate(),np.random.get_state(),torch.get_rng_state())
    callback.evaluate_checkpoint(checkpoint,final=True)
    assert random.getstate()==before[0]
    assert np.array_equal(np.random.get_state()[1],before[1][1])
    assert torch.equal(torch.get_rng_state(),before[2])
