"""One CPU process, one PPO driver, several in-process environments."""
import argparse
from collections import deque
import csv
from dataclasses import asdict, dataclass
import os
import random
from pathlib import Path
import signal
import time
import traceback
from uuid import uuid4
import torch
import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
from ..config import TRAINING as T
from ..sim import SIM_VERSION
from .env import RacingEnv
from .evaluate import evaluate
from .runtime import configure_torch, set_priority
from .storage import (atomic_json,read_json,run_path,writer_lock,ensure_freeze,
                      latest_checkpoint,validate_checkpoint,save_checkpoint)


class StopRequest:
    def __init__(self, path: Path | None):
        self.path=path
        self.requested=False

    def signal(self, *_):
        self.requested=True

    def __call__(self) -> bool:
        return self.requested or (self.path is not None and self.path.exists())


@dataclass
class LearningRate:
    base_seconds: float
    hours: float
    started: float

    def __call__(self, progress_remaining):
        used=max(1-progress_remaining,min(1.,(self.base_seconds+time.perf_counter()-self.started)/(self.hours*3600)))
        return T.learning_rate+(T.final_learning_rate-T.learning_rate)*used


class TrainingCallback(BaseCallback):
    def __init__(self, args, run: Path, stop: StopRequest, previous: dict):
        super().__init__()
        self.args,self.run,self.stop=args,run,stop
        self.started=time.perf_counter()
        self.cpu_started=time.process_time()
        self.base_seconds=float(previous.get('training_seconds',0.))
        self.base_cpu=float(previous.get('cpu_seconds',0.))
        self.training_laps=int(previous.get('training_laps',0))
        self.best=previous.get('best_lap')
        self.eval_result=previous.get('evaluation',{})
        self.rewards=deque(maxlen=100)
        self.last_status=0.
        self.last_steps=int(previous.get('steps',0))
        self.last_clock=self.started
        self.sps=0.
        self.phase='training'
        self.next_checkpoint=0

    @property
    def seconds(self):
        return self.base_seconds+time.perf_counter()-self.started

    def metadata(self) -> dict:
        return {'car_id':self.args.car_id,'track_id':self.args.track_id,
                'training_seconds':self.seconds,'cpu_seconds':self.base_cpu+time.process_time()-self.cpu_started,
                'training_laps':self.training_laps,'best_lap':self.best,'evaluation':self.eval_result,
                'hyperparameters':dict(asdict(T),n_envs=self.args.n_envs,rollout_steps=self.args.rollout_steps,
                                       batch_size=self.args.batch_size,epochs=self.args.epochs,
                                       checkpoint_steps=self.args.checkpoint_steps,evaluate_every=self.args.evaluate_every,
                                       evaluation_episodes=self.args.eval_episodes,total_steps=self.args.steps,hours=self.args.hours),
                'seed':self.args.seed,'experiment':self.args.experiment,'worker_token':self.args.worker_token}

    def write_status(self, status: str | None = None, error: str | None = None) -> None:
        now=time.perf_counter()
        if now>self.last_clock and self.model.num_timesteps>self.last_steps:
            self.sps=(self.model.num_timesteps-self.last_steps)/(now-self.last_clock)
        self.last_clock=now; self.last_steps=self.model.num_timesteps
        data=dict(self.metadata(),steps=self.model.num_timesteps,steps_per_second=self.sps,
                  mean_reward=sum(self.rewards)/len(self.rewards) if self.rewards else None,
                  status=status or self.phase,pid=os.getpid(),updated_at=time.time(),sim_version=SIM_VERSION,error=error)
        atomic_json(self.run/'status.json',data)
        path=self.run/'logs'/'progress.csv'
        path.parent.mkdir(exist_ok=True)
        fields=('steps','training_seconds','steps_per_second','mean_reward','training_laps','best_lap','mean_lap','completion_rate','status')
        row={key:data.get(key) for key in fields}
        row.update(mean_lap=self.eval_result.get('mean_lap'),completion_rate=self.eval_result.get('completion_rate'))
        exists=path.exists() and path.stat().st_size>0
        with path.open('a',newline='',encoding='utf-8') as stream:
            writer=csv.DictWriter(stream,fieldnames=fields)
            if not exists: writer.writeheader()
            writer.writerow(row)
        self.last_status=now

    def checkpoint(self) -> Path:
        return save_checkpoint(self.model,self.training_env,self.run,self.metadata())

    def evaluate_checkpoint(self, checkpoint: Path, *, final: bool = False):
        if self.stop(): return
        self.phase='evaluating'; self.write_status()
        def evaluation_stop():
            if time.perf_counter()-self.last_status>=T.status_seconds:
                self.write_status()
            return self.stop() or (not final and self.seconds>=self.args.hours*3600)
        # Loading a separate PPO object seeds global RNGs. Evaluation must not
        # reset the randomness of the still-running training process.
        rng=(random.getstate(),np.random.get_state(),torch.get_rng_state())
        try:
            self.eval_result=evaluate(checkpoint,self.args.eval_episodes,evaluation_stop)
        finally:
            random.setstate(rng[0]); np.random.set_state(rng[1]); torch.set_rng_state(rng[2])
        result=dict(self.eval_result,steps=self.model.num_timesteps,checkpoint=checkpoint.name)
        atomic_json(checkpoint/'evaluation.json',result)
        history=self.run/'logs'/'lap_history.csv'
        exists=history.exists() and history.stat().st_size>0
        with history.open('a',newline='',encoding='utf-8') as stream:
            writer=csv.DictWriter(stream,fieldnames=('steps','best_lap','mean_lap','completion_rate','episodes','checkpoint'))
            if not exists: writer.writeheader()
            writer.writerow({key:result[key] for key in writer.fieldnames})
        # Prefer reliability before speed. The pointer retains the exact bundle,
        # including its normalization statistics; checkpoints are never pruned.
        previous=read_json(self.run/'best.json',{})
        score=(result['completion_rate'],-(result['mean_lap'] or float('inf')))
        old_score=(previous.get('completion_rate',0),-(previous.get('mean_lap') or float('inf')))
        if result['completed_laps'] and score>old_score:
            atomic_json(self.run/'best.json',result)
        if result['best_lap'] is not None:
            self.best=min(self.best,result['best_lap']) if self.best is not None else result['best_lap']
        self.phase='training'
        self.write_status()

    def _on_training_start(self):
        self.next_checkpoint=(self.model.num_timesteps//self.args.checkpoint_steps+1)*self.args.checkpoint_steps
        self.last_steps=self.model.num_timesteps
        self.write_status()

    def _on_step(self) -> bool:
        for info in self.locals.get('infos',[]):
            self.training_laps+=int(info.get('lap_completed',False))
            if 'episode' in info:
                self.rewards.append(float(info['episode']['r']))
        if self.model.num_timesteps>=self.next_checkpoint:
            checkpoint=self.checkpoint()
            number=self.model.num_timesteps//self.args.checkpoint_steps
            self.next_checkpoint=(number+1)*self.args.checkpoint_steps
            if self.args.evaluate_every and number%self.args.evaluate_every==0:
                self.evaluate_checkpoint(checkpoint)
        if time.perf_counter()-self.last_status>=T.status_seconds:
            self.write_status()
        return not (self.stop() or self.seconds>=self.args.hours*3600 or self.model.num_timesteps>=self.args.steps)


def train(args) -> Path | None:
    args.worker_token=args.worker_token or uuid4().hex
    configure_torch(); set_priority(args.priority)
    run=run_path(args.root,args.car_id,args.track_id)
    ensure_freeze(args.root,args.experiment)
    stop=StopRequest(args.stop_file)
    for name in ('SIGINT','SIGTERM','SIGBREAK'):
        if hasattr(signal,name): signal.signal(getattr(signal,name),stop.signal)
    with writer_lock(run):
        checkpoint=latest_checkpoint(run,car_id=args.car_id,track_id=args.track_id) if args.resume else None
        if not args.resume and (run/'checkpoints').exists() and any((run/'checkpoints').glob('step_*')):
            raise ValueError('This run already has checkpoints. Use --resume or a new --root.')
        previous=validate_checkpoint(checkpoint) if checkpoint else {}
        status=read_json(run/'status.json',{})
        if checkpoint and status.get('sim_version')==SIM_VERSION:
            for key in ('training_seconds','cpu_seconds','training_laps'):
                previous[key]=max(previous.get(key,0),status.get(key,0))
            for key in ('best_lap','evaluation'):
                if status.get(key) is not None: previous[key]=status[key]
        base=DummyVecEnv([lambda:RacingEnv(args.car_id,args.track_id) for _ in range(args.n_envs)])
        base.seed(args.seed)
        normalizer=VecNormalize.load(checkpoint/'vecnormalize.pkl',base) if checkpoint else VecNormalize(base,norm_obs=True,norm_reward=True,gamma=T.gamma)
        normalizer.training=True; normalizer.norm_reward=True
        callback=TrainingCallback(args,run,stop,previous)

        learning_rate=LearningRate(callback.base_seconds,args.hours,callback.started)

        if checkpoint:
            model=PPO.load(checkpoint/'model.zip',env=normalizer,device='cpu',
                           n_steps=args.rollout_steps,batch_size=args.batch_size,n_epochs=args.epochs)
            model.lr_schedule=learning_rate
            model.learning_rate=learning_rate
        else:
            model=PPO('MlpPolicy',normalizer,device='cpu',seed=args.seed,
                      policy_kwargs={'net_arch':list(T.hidden_layers),'activation_fn':torch.nn.Tanh},
                      n_steps=args.rollout_steps,batch_size=args.batch_size,n_epochs=args.epochs,
                      gamma=T.gamma,gae_lambda=T.gae_lambda,learning_rate=learning_rate,
                      ent_coef=T.entropy,clip_range=T.clip_range,verbose=0)
        callback.init_callback(model)
        final_status='completed'
        error=None
        print(f'CPU worker car={args.car_id+1} track={args.track_id+1}, resume={model.num_timesteps:,} steps, sim={SIM_VERSION}',flush=True)
        try:
            if model.num_timesteps<args.steps and callback.seconds<args.hours*3600 and not stop():
                model.learn(total_timesteps=args.steps-model.num_timesteps,callback=callback,reset_num_timesteps=False)
            if stop(): final_status='stopped'
        except KeyboardInterrupt:
            stop.requested=True; final_status='stopped'
        except Exception:
            final_status='failed'; error=traceback.format_exc()
        finally:
            try:
                checkpoint=callback.checkpoint()
                if args.eval_episodes and final_status=='completed':
                    callback.evaluate_checkpoint(checkpoint,final=True)
                callback.write_status(final_status,error)
            finally:
                normalizer.close()
        if error: raise RuntimeError(error)
        print(f'{final_status.upper()}: {model.num_timesteps:,} steps; checkpoint={checkpoint}',flush=True)
        return checkpoint


def parser() -> argparse.ArgumentParser:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--car-id',type=int,choices=range(5),required=True)
    p.add_argument('--track-id',type=int,choices=range(5),required=True)
    p.add_argument('--root',type=Path,default=Path('runs'))
    p.add_argument('--hours',type=float,default=T.hours)
    p.add_argument('--steps',type=int,default=T.total_steps)
    p.add_argument('--n-envs',type=int,default=T.n_envs)
    p.add_argument('--rollout-steps',type=int,default=T.rollout_steps)
    p.add_argument('--batch-size',type=int,default=T.batch_size)
    p.add_argument('--epochs',type=int,default=T.epochs)
    p.add_argument('--checkpoint-steps',type=int,default=T.checkpoint_steps)
    p.add_argument('--evaluate-every',type=int,default=T.evaluate_every)
    p.add_argument('--eval-episodes',type=int,default=T.evaluation_episodes)
    p.add_argument('--seed',type=int,default=T.seed)
    p.add_argument('--priority',choices=('below-normal','idle','normal'),default='below-normal')
    p.add_argument('--resume',action='store_true')
    p.add_argument('--experiment',action='store_true',help='Disposable sanity/benchmark run; do not establish physics freeze')
    p.add_argument('--stop-file',type=Path)
    p.add_argument('--worker-token',default=None,help=argparse.SUPPRESS)
    return p


def main():
    p=parser(); args=p.parse_args()
    for name in ('hours','steps','n_envs','rollout_steps','batch_size','epochs','checkpoint_steps'):
        if getattr(args,name)<=0: p.error(f'{name} must be positive')
    if args.n_envs*args.rollout_steps<2 or args.batch_size<2:
        p.error('Rollout size and batch size must be at least two')
    if args.eval_episodes<0 or args.evaluate_every<0: p.error('Evaluation values cannot be negative')
    train(args)
