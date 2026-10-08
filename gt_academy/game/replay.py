"""Bounded presentation snapshots; playback never advances a simulation."""
from collections import deque
from dataclasses import replace
from .debug_viewer import interpolate_state
from .config import CLIENT
from ..config import PHYSICS


class Replay:
    def __init__(self,seconds=CLIENT.replay_seconds):
        self.hz=1/(PHYSICS.dt*CLIENT.replay_stride)
        self.frames=deque(maxlen=round(seconds*self.hz)+1)
        self.playhead=0.
        self.paused=False

    def record(self,session):
        state=session.sim.state
        if state.ticks%CLIENT.replay_stride: return
        other=getattr(session,'opponent',None)
        self.frames.append((replace(state),replace(other.sim.state) if other else None))

    @property
    def duration(self): return max(0,(len(self.frames)-1)/self.hz)

    def start(self):
        self.playhead=0.
        self.paused=False

    def update(self,dt):
        if not self.paused: self.playhead=min(self.duration,self.playhead+dt)
        return self.playhead>=self.duration

    def at(self):
        if not self.frames: return None,None
        index=min(len(self.frames)-1,int(self.playhead*self.hz))
        following=min(index+1,len(self.frames)-1)
        fraction=self.playhead*self.hz-index
        a,b=self.frames[index],self.frames[following]
        return (interpolate_state(a[0],b[0],fraction),
                interpolate_state(a[1],b[1],fraction) if a[1] is not None and b[1] is not None else None)
