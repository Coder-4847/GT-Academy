"""Tiny real-worker save/resume/stop bug check, never a learning benchmark."""
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4
if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gt_academy.rl.runtime import configure_environment
configure_environment()
from gt_academy.rl.storage import read_json,run_path,latest_checkpoint,validate_checkpoint,atomic_json
from gt_academy.rl.launcher import terminate_worker


def main():
    root=Path('artifacts')/('worker_verification_'+uuid4().hex[:8])
    root.mkdir(parents=True)
    base=[sys.executable,'-m','tools.train_one','--car-id','0','--track-id','0',
          '--root',str(root),'--n-envs','2','--rollout-steps','8','--batch-size','16','--epochs','1',
          '--checkpoint-steps','16','--evaluate-every','0','--eval-episodes','0',
          '--hours','.02','--experiment']
    print('BUG CHECK ONLY: tiny PPO updates, serialization, resume and graceful stop.',flush=True)
    for target in (32,48):
        command=base+['--steps',str(target)]+(['--resume'] if target==48 else [])
        result=subprocess.run(command,capture_output=True,text=True,timeout=45)
        if result.returncode: raise RuntimeError(result.stdout+result.stderr)
        print(result.stdout.strip(),flush=True)
        metadata=validate_checkpoint(latest_checkpoint(run_path(root,0,0)))
        assert metadata['steps']==target
    stop=root/'STOP'
    log=root/'stop-check.log'
    token=uuid4().hex
    with log.open('w',encoding='utf-8') as output:
        process=subprocess.Popen(base+['--steps','1000000','--resume','--stop-file',str(stop),'--worker-token',token],stdout=output,stderr=subprocess.STDOUT)
        try:
            deadline=time.monotonic()+30
            while time.monotonic()<deadline:
                status=read_json(run_path(root,0,0)/'status.json',{})
                if status.get('worker_token')==token and status.get('status')=='training': break
                if process.poll() is not None: raise RuntimeError('Worker exited before stop request')
                time.sleep(.05)
            else: raise TimeoutError('Worker did not publish a startup status')
            stop.write_text('Graceful stop bug check',encoding='utf-8')
            assert process.wait(timeout=30)==0
        finally:
            if process.poll() is None:
                stop.write_text('Stop verification on error',encoding='utf-8')
                try: process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    terminate_worker(process); process.wait(timeout=10)
    status=read_json(run_path(root,0,0)/'status.json')
    metadata=validate_checkpoint(latest_checkpoint(run_path(root,0,0)))
    assert status['status']=='stopped' and metadata['steps']==status['steps']
    result={'result':'passed','root':str(root.resolve()),'stopped_at_steps':status['steps'],
            'sim_version':metadata['sim_version'],'checks':['real PPO update','save','resume','graceful stop file','final checkpoint']}
    atomic_json(root/'verification.json',result)
    print(f'PASS: final checkpoint at {status["steps"]} steps after stop request. Root: {root.resolve()}',flush=True)
    print('No learning-quality, laptop-throughput or temperature claim. Ctrl+C invokes the same worker stop mechanism.')


if __name__=='__main__': main()
