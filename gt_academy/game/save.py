"""Player data only. Never writes to or imports the training storage layer."""
from copy import deepcopy
import json
import math
from pathlib import Path
from ..sim import SIM_VERSION
from .config import DEFAULT_SETTINGS, CLIENT


class PlayerSave:
    def __init__(self,path: Path):
        self.path=Path(path)
        self.settings=deepcopy(DEFAULT_SETTINGS)
        self.records={}
        self.medals={}
        self.race_bests={}
        self.warning=''
        try:
            raw=json.loads(self.path.read_text(encoding='utf-8'))
            settings=raw.get('settings',{})
            if not isinstance(settings,dict): raise ValueError('Invalid settings')
            for name in ('master','engine','effects'):
                value=settings.get(name,self.settings[name])
                if isinstance(value,(int,float)) and math.isfinite(value):
                    self.settings[name]=max(0.,min(1.,value))
            for name in ('mute','assist','fullscreen'):
                if isinstance(settings.get(name),bool): self.settings[name]=settings[name]
            for name,low,high in (('ai_noise',0,1),('ai_penalty',0,60),('race_laps',1,5),('rival_car',0,4)):
                value=settings.get(name,self.settings[name])
                if isinstance(value,(float,int)) and math.isfinite(value):
                    self.settings[name]=max(low,min(high,value))
            self.settings['race_laps']=int(self.settings['race_laps'])
            self.settings['rival_car']=int(self.settings['rival_car'])
            if settings.get('rival_tier') in ('Rookie','Pro','Champion','Legend'): self.settings['rival_tier']=settings['rival_tier']
            if isinstance(settings.get('ai_ghost'),bool): self.settings['ai_ghost']=settings['ai_ghost']
            if settings.get('quality') in ('High','Medium','Low'): self.settings['quality']=settings['quality']
            bindings=settings.get('bindings',{})
            if isinstance(bindings,dict):
                for name,key in bindings.items():
                    if name in self.settings['bindings'] and isinstance(key,int) and 0<key<2**31:
                        self.settings['bindings'][name]=key
            if raw.get('sim_version')==SIM_VERSION and isinstance(raw.get('records'),dict):
                for key,record in raw['records'].items():
                    if self.valid_record(record): self.records[key]=record
            if raw.get('sim_version')==SIM_VERSION and isinstance(raw.get('medals'),dict):
                for key,value in raw['medals'].items():
                    if key in {f'{t}:{tier}' for t in range(5) for tier in ('Rookie','Pro','Champion','Legend')} and isinstance(value,(float,int)) and math.isfinite(value) and value>0:
                        self.medals[key]=value
            if raw.get('sim_version')==SIM_VERSION and isinstance(raw.get('race_bests'),dict):
                for key,value in raw['race_bests'].items():
                    if isinstance(value,(float,int)) and math.isfinite(value) and value>0: self.race_bests[key]=value
        except FileNotFoundError:
            pass
        except (OSError,ValueError,TypeError,AttributeError):
            self.warning='Save could not be read. Using default settings.'

    @staticmethod
    def valid_record(record):
        if not isinstance(record,dict): return False
        seconds=record.get('time')
        samples=record.get('ghost')
        if not isinstance(seconds,(int,float)) or not math.isfinite(seconds) or seconds<=0: return False
        if not isinstance(samples,list) or not 2<=len(samples)<=CLIENT.max_ghost_samples: return False
        previous=-1
        for row in samples:
            if not isinstance(row,list) or len(row)!=6: return False
            if not all(isinstance(x,(int,float)) and math.isfinite(x) for x in row): return False
            if row[0]<previous or row[0]<0 or row[0]>seconds+.05: return False
            previous=row[0]
        return True

    def record(self,car,track):
        return self.records.get(f'{track}:{car}')

    def best(self,car,track):
        record=self.record(car,track)
        return record['time'] if record else None

    def submit(self,car,track,seconds,ghost):
        record={'time':seconds,'ghost':ghost}
        if not self.valid_record(record): return False
        previous=self.best(car,track)
        if previous is not None and previous<=seconds: return False
        self.records[f'{track}:{car}']=record
        self.flush()
        return True

    def flush(self):
        try:
            self.path.parent.mkdir(parents=True,exist_ok=True)
            temporary=self.path.with_suffix('.tmp')
            temporary.write_text(json.dumps({'schema':1,'sim_version':SIM_VERSION,
                'settings':self.settings,'records':self.records,'medals':self.medals,'race_bests':self.race_bests},allow_nan=False),encoding='utf-8')
            temporary.replace(self.path)
            self.warning=''
            return True
        except OSError:
            self.warning='Could not save to disk. This session is still playable.'
            return False

    def award(self,track,tier,seconds):
        from .racing import unlocked
        if not isinstance(seconds,(int,float)) or not math.isfinite(seconds) or seconds<=0: return False
        if not unlocked(self.medals,track,tier): return False
        key=f'{track}:{tier}'
        self.medals[key]=min(seconds,self.medals.get(key,float('inf')))
        self.flush()
        return True
