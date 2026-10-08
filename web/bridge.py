"""Browser adapter. The original simulation and session implementations are reused."""
from dataclasses import asdict
import json
from pathlib import Path
import numpy as np
from gt_academy.sim import SIM_VERSION,require_version
from gt_academy.config import PHYSICS,VIEWER
from gt_academy.sim.physics import approach,clamp
from gt_academy.game.save import PlayerSave
from gt_academy.game.session import Session
from gt_academy.game.racing import RaceSession,AIGhostSession


class NumpyDriver:
    def __init__(self,path,car,track):
        with np.load(path,allow_pickle=False) as data: self.data={k:data[k] for k in data.files}
        require_version(str(self.data['sim_version']))
        if int(self.data['car'])!=car or int(self.data['track'])!=track: raise ValueError('Opponent identity mismatch')

    def action(self,raw):
        d=self.data
        x=np.clip((raw-d['mean'])/np.sqrt(d['var']+d['epsilon']),-d['clip'],d['clip']).astype(np.float32)
        for i in range(3):
            x=d[f'weight{i}']@x+d[f'bias{i}']
            if i<2: x=np.tanh(x)
        return np.clip(x,-1,1)

    def close(self): pass


class BrowserGame:
    def __init__(self,profile_path='/profile.json'):
        self.session=None
        self.steer=0.
        self.profile_path=Path(profile_path)

    def start(self,options_json,profile_json='{}'):
        o=json.loads(options_json)
        self.profile_path.write_text(profile_json,encoding='utf-8')
        self.save=PlayerSave(self.profile_path)
        car,track,mode=o['car'],o['track'],o['mode']
        if self.session and hasattr(self.session,'close'): self.session.close()
        if mode in ('Race vs AI','Career') or (mode=='Time Trial' and o.get('aiGhost')):
            driver=NumpyDriver('/opponent.npz',o['rival'],track)
            if mode=='Time Trial': self.session=AIGhostSession(car,track,self.save,driver,o['rival'])
            else: self.session=RaceSession(car,track,mode,self.save,driver,o['rival'],o['tier'],o['laps'],o.get('penalty',0))
        else: self.session=Session(car,track,mode,self.save)
        self.steer=0.
        self.profile_signature=None
        return self.snapshot()

    def step(self,left,pedal,ticks,assist=False):
        for _ in range(min(6,max(0,int(ticks)))):
            self.steer=approach(self.steer,left,VIEWER.keyboard_rate*PHYSICS.dt)
            steer=self.steer
            if assist and abs(self.session.sim.state.vx)>3: steer-=clamp(self.session.sim.state.slip_rear,-.5,.5)*.1
            self.session.step((clamp(steer,-1,1),clamp(pedal,-1,1)))
        return self.snapshot()

    def reset(self):
        if self.session.mode!='Free Practice': raise ValueError('Restart this session from the pause menu.')
        self.session.reset_to_track(); self.steer=0.
        return self.snapshot()

    def snapshot(self):
        s=self.session; lap=s.sim.lap
        result=dict(state=asdict(s.sim.state),previous=asdict(s.previous),laps=lap.lap_times,lapTime=lap.elapsed,
            valid=lap.valid,countdown=s.countdown,finished=s.finished,best=self.save.best(s.car_id,s.track_id),
            newBest=s.new_best,result=getattr(s,'result',''),mode=s.mode)
        opponent=getattr(s,'opponent',None)
        if opponent:
            result.update(opponent=asdict(opponent.sim.state),opponentPrevious=asdict(opponent.previous),
                opponentLaps=opponent.sim.lap.lap_times,opponentFinish=opponent.finish_time,dnf=opponent.dnf)
        if isinstance(s,RaceSession): result.update(position=s.position,gap=s.gap,playerFinish=s.player_finish,penalty=s.penalty)
        if s.ghost and not isinstance(s,AIGhostSession):
            ghost=s.ghost.at(lap.elapsed)
            if ghost: result['ghost']=asdict(ghost)
        signature=(len(lap.lap_times),s.finished,len(self.save.medals))
        if signature!=getattr(self,'profile_signature',None):
            self.profile_signature=signature
            result['profile']=json.dumps(dict(sim_version=SIM_VERSION,settings=self.save.settings,records=self.save.records,medals=self.save.medals,race_bests=self.save.race_bests))
        return json.dumps(result)


game=BrowserGame()
