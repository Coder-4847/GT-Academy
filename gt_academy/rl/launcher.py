"""Windows-safe bounded worker launcher with checkpoint recovery and stop files."""
import argparse
from collections import deque
import ctypes
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
from uuid import uuid4
from ..config import TRAINING as T
from ..cars import CARS
from ..tracks import TRACKS
from ..sim import SIM_VERSION
from .catalog import pairs
from .storage import run_path,atomic_json,read_json,ensure_freeze,writer_lock


class CpuSampler:
    """Windows system CPU use via the OS, avoiding another dependency."""
    def __init__(self):
        self.previous=self.snapshot()

    @staticmethod
    def snapshot():
        if os.name!='nt': return None
        from ctypes import wintypes
        idle,kernel,user=wintypes.FILETIME(),wintypes.FILETIME(),wintypes.FILETIME()
        if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle),ctypes.byref(kernel),ctypes.byref(user)):
            return None
        number=lambda value:(value.dwHighDateTime<<32)|value.dwLowDateTime
        return number(idle),number(kernel)+number(user)

    def sample(self):
        now=self.snapshot(); old=self.previous; self.previous=now
        if now is None or old is None or now[1]<=old[1]: return None
        return max(0.,min(100.,100*(1-(now[0]-old[0])/(now[1]-old[1]))))


def worker_command(args,car: int,track: int,stop_file: Path,token: str = 'dry-run') -> list[str]:
    command=[sys.executable,'-m','tools.train_one','--car-id',str(car),'--track-id',str(track),
             '--root',str(args.root.resolve()),'--hours',str(args.hours),'--steps',str(args.steps),
             '--n-envs',str(args.n_envs),'--priority',args.priority,'--resume','--stop-file',str(stop_file.resolve()),
             '--checkpoint-steps',str(args.checkpoint_steps),'--evaluate-every',str(args.evaluate_every),
             '--eval-episodes',str(args.eval_episodes),'--seed',str(args.seed+track*5+car),
             '--worker-token',token]
    if args.experiment: command.append('--experiment')
    return command


def terminate_worker(process) -> None:
    """Windows venv python.exe is a redirector; terminate its owned tree."""
    if process.poll() is not None: return
    if os.name=='nt':
        subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],
                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10)
    else:
        process.kill()


def preflight(args, count: int) -> None:
    free=shutil.disk_usage(args.root.resolve().anchor).free/1024**3
    # Conservative 5 MiB bundle allowance until an actual trained checkpoint
    # can be measured. Retention is deliberately lossless for tier building.
    expected=count*(math.ceil(args.steps/args.checkpoint_steps)+2)*5/1024
    print('\nPRE-FLIGHT (check these yourself before an overnight run)',flush=True)
    print(f'  Output root: {args.root.resolve()}',flush=True)
    print('  Plug in AC; select Performance mode; keep vents clear.',flush=True)
    print('  Disable sleep while plugged in; prevent overnight update restarts.',flush=True)
    print('  Watch temperatures in your laptop utility during the sanity/benchmark runs.',flush=True)
    print(f'  Free disk: {free:.1f} GiB. Conservative checkpoint allowance: {expected:.1f} GiB.',flush=True)
    print(f'  {count} runs, cap {args.max_concurrent}; each gets up to {args.hours:g} active hours or {args.steps:,} lifetime steps.',flush=True)
    print(f'  Waves may take up to {math.ceil(count/args.max_concurrent)*args.hours:g} wall-clock hours plus evaluation/startup.',flush=True)
    print('  CPU only, one torch/BLAS thread per worker. Ctrl+C requests final checkpoints.',flush=True)
    if free<expected+2: print('  WARNING: free space is below the conservative allowance.',flush=True)


def launch(args) -> dict:
    selected=pairs(args.cars,args.tracks)
    args.root.mkdir(parents=True,exist_ok=True)
    # One orchestration process per root; OS lock releases on crashes.
    with writer_lock(args.root/'_launcher'):
        return _launch_locked(args,selected)


def _launch_locked(args,selected) -> dict:
    preflight(args,len(selected))
    ensure_freeze(args.root,args.experiment)
    session=uuid4().hex[:12]
    stop_file=args.root/f'.stop-{session}'
    pending=deque(selected)
    running={}
    jobs={f'{t}:{c}':{'car_id':c,'track_id':t,'status':'queued','restarts':0} for c,t in selected}
    started=time.monotonic(); last_publish=0.
    stopping=False; stop_started=None
    requested=[False]
    cpu=CpuSampler(); cpu_samples=[]
    previous_signals={}

    def request_stop(*_): requested[0]=True
    for name in ('SIGINT','SIGTERM','SIGBREAK'):
        if hasattr(signal,name):
            sig=getattr(signal,name)
            previous_signals[sig]=signal.signal(sig,request_stop)

    def event(kind,car=None,track=None,**extra):
        data=dict(time=time.time(),event=kind,car_id=car,track_id=track,**extra)
        with (args.root/'launcher_events.jsonl').open('a',encoding='utf-8') as stream:
            stream.write(json.dumps(data)+'\n')
        print(f'{kind}: '+(f'{TRACKS[track].spec.name} / {CARS[car].name} ' if car is not None else '')+str(extra or ''),flush=True)

    def publish():
        atomic_json(args.root/'launcher.json',{'session':session,'pid':os.getpid(),'updated_at':time.time(),
                    'status':'stopping' if stopping else ('running' if running or pending else 'finished'),
                    'sim_version':SIM_VERSION,'jobs':list(jobs.values()),'stop_file':str(stop_file.resolve())})

    try:
        while pending or running:
            if requested[0] and not stopping:
                stopping=True; stop_started=time.monotonic()
                stop_file.write_text('Graceful stop requested\n',encoding='utf-8')
                event('STOP_REQUESTED')
                for car,track in pending: jobs[f'{track}:{car}']['status']='not_started'
                pending.clear()
            while pending and len(running)<args.max_concurrent and not stopping:
                car,track=pending.popleft(); key=f'{track}:{car}'
                run=run_path(args.root,car,track); run.mkdir(parents=True,exist_ok=True)
                console=(run/'worker.log').open('a',encoding='utf-8')
                flags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name=='nt' else 0
                token=uuid4().hex
                try:
                    process=subprocess.Popen(worker_command(args,car,track,stop_file,token),
                        cwd=Path(__file__).resolve().parents[2],stdout=console,stderr=subprocess.STDOUT,
                        creationflags=flags)
                except Exception:
                    console.close(); raise
                running[key]=(process,console,car,track)
                jobs[key].update(status='running',pid=process.pid,worker_token=token)
                event('START',car,track,pid=process.pid)
            for key,(process,console,car,track) in list(running.items()):
                code=process.poll()
                if code is None:
                    if stopping and time.monotonic()-stop_started>T.stop_grace_seconds:
                        terminate_worker(process)
                        event('UNRESPONSIVE_TERMINATED',car,track,warning='Final checkpoint could not be guaranteed; last complete bundle retained.')
                    continue
                console.close(); del running[key]
                if code!=0 and not stopping and jobs[key]['restarts']<T.restart_limit:
                    jobs[key]['restarts']+=1; jobs[key]['status']='queued'
                    pending.append((car,track))
                    event('RESTART',car,track,exit_code=code,attempt=jobs[key]['restarts'])
                else:
                    state=read_json(run_path(args.root,car,track)/'status.json',{})
                    status=('stopped' if stopping else 'completed') if code==0 else 'failed'
                    if code==0 and state.get('status')=='stopped': status='stopped'
                    jobs[key].update(status=status,exit_code=code)
                    event(status.upper(),car,track,exit_code=code)
            if time.monotonic()-last_publish>=1:
                publish(); last_publish=time.monotonic()
                utilization=cpu.sample()
                if utilization is not None: cpu_samples.append(utilization)
            time.sleep(.2)
    finally:
        # An orchestration exception must still ask surviving children to save.
        if running:
            stop_file.write_text('Launcher exiting; save and stop\n',encoding='utf-8')
            deadline=time.monotonic()+T.stop_grace_seconds
            for process,console,_,_ in running.values():
                try: process.wait(timeout=max(.1,deadline-time.monotonic()))
                except subprocess.TimeoutExpired:
                    terminate_worker(process); process.wait(timeout=10)
                console.close()
        for sig,handler in previous_signals.items(): signal.signal(sig,handler)
        publish()
    summary={'jobs':list(jobs.values()),'elapsed_seconds':time.monotonic()-started,
             'cpu_percent':sum(cpu_samples)/len(cpu_samples) if cpu_samples else None,
             'stopped':stopping,'session':session,'sim_version':SIM_VERSION}
    atomic_json(args.root/'launch_summary.json',summary)
    return summary


def parser():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('runs'))
    p.add_argument('--cars',default='all',help='Comma-separated names or 1–5')
    p.add_argument('--tracks',default='all',help='Comma-separated names, underscore slugs, or 1–5')
    p.add_argument('--hours',type=float,default=T.hours)
    p.add_argument('--steps',type=int,default=T.total_steps)
    p.add_argument('--max-concurrent',type=int,default=T.max_concurrent)
    p.add_argument('--n-envs',type=int,default=T.n_envs)
    p.add_argument('--priority',choices=('below-normal','idle','normal'),default='below-normal')
    p.add_argument('--checkpoint-steps',type=int,default=T.checkpoint_steps)
    p.add_argument('--evaluate-every',type=int,default=T.evaluate_every)
    p.add_argument('--eval-episodes',type=int,default=T.evaluation_episodes)
    p.add_argument('--seed',type=int,default=T.seed)
    p.add_argument('--experiment',action='store_true')
    p.add_argument('--dry-run',action='store_true',help='Print selections and commands without starting workers or freezing physics')
    return p


def main():
    p=parser(); args=p.parse_args()
    for field in ('hours','steps','max_concurrent','n_envs','checkpoint_steps'):
        if getattr(args,field)<=0: p.error(f'{field} must be positive')
    if args.eval_episodes<0 or args.evaluate_every<0: p.error('Evaluation values cannot be negative')
    try: selected=pairs(args.cars,args.tracks)
    except ValueError as error: p.error(str(error))
    if args.dry_run:
        preflight(args,len(selected))
        for car,track in selected:
            print(subprocess.list2cmdline(worker_command(args,car,track,args.root/'.dry-run-stop')))
        return
    summary=launch(args)
    failed=sum(job['status']=='failed' for job in summary['jobs'])
    print(f'FINISHED: {len(summary["jobs"])} selected; {failed} failed. See {args.root / "launch_summary.json"}.',flush=True)
    if failed: raise SystemExit(1)
