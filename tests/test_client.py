"""Phase 3 integration checks. All writes use disposable player-save paths."""
from dataclasses import asdict
import json
import math
import os
from pathlib import Path
from uuid import uuid4
import pytest
from gt_academy.sim import SIM_VERSION
from gt_academy.config import PHYSICS as P
from gt_academy.game.save import PlayerSave
from gt_academy.game.session import Session,Ghost


@pytest.fixture
def tmp_path():
    # Keep sandbox verification writes inside the workspace, away from runs.
    path=Path('artifacts')/f'client_test_{uuid4().hex[:10]}'
    path.mkdir(parents=True)
    return path


def test_player_save_roundtrip_corruption_and_version(tmp_path):
    path=tmp_path/'profile.json'
    save=PlayerSave(path)
    rows=[[0.,0.,0.,0.,0.,0.],[10.,10.,0.,.1,0.,100.]]
    assert save.submit(0,0,10,rows)
    assert not save.submit(0,0,11,rows)
    save.settings.update(quality='Low',master=.2)
    assert save.flush()
    loaded=PlayerSave(path)
    assert loaded.best(0,0)==10
    assert loaded.settings['master']==.2
    assert loaded.record(1,0) is None
    data=json.loads(path.read_text())
    data['sim_version']='old'
    path.write_text(json.dumps(data))
    loaded=PlayerSave(path)
    assert loaded.best(0,0) is None and loaded.settings['quality']=='Low'
    path.write_text('broken{')
    assert PlayerSave(path).warning


@pytest.mark.parametrize('bad',([0],{'time':float('nan'),'ghost':[]},
    {'time':10,'ghost':[[0,0,0,0,0,0],[2,float('inf'),0,0,0,0]]},
    {'time':10,'ghost':[[2,0,0,0,0,0],[1,0,0,0,0,0]]}))
def test_corrupt_ghosts_are_rejected(bad):
    assert not PlayerSave.valid_record(bad)


def test_ghost_interpolates_wrap_and_progress_delta():
    ghost=Ghost({'ghost':[[0,0,0,math.pi-.1,0,0],[10,10,20,-math.pi+.1,.2,100]]})
    s=ghost.at(5)
    assert (s.x,s.y,s.heading)==pytest.approx((5,10,math.pi))
    assert ghost.delta(6,50)==pytest.approx(1)
    assert ghost.at(11) is None


def test_countdown_and_practice_reset(tmp_path):
    save=PlayerSave(tmp_path/'save.json')
    session=Session(0,0,'Time Trial',save)
    before=asdict(session.sim.state)
    for _ in range(180): session.step((1,1))
    assert session.countdown==0
    assert asdict(session.sim.state)==before
    assert session.sim.lap.elapsed==0
    session.step((0,1))
    assert session.sim.state.ticks==1
    assert not session.reset_to_track()
    session=Session(1,1,'Free Practice',save)
    session.sim.state.offset=7
    assert session.reset_to_track()
    assert session.sim.state.vx==session.sim.state.offset==0
    assert not session.sim.lap.valid
    assert not save.path.exists()


def test_actual_three_lap_session_saves_and_replays_ghost(tmp_path):
    save=PlayerSave(tmp_path/'save.json')
    session=Session(0,0,'Time Trial',save)
    for _ in range(20000):
        s=session.sim.state
        point,_,_=session.sim.track.at(s.progress+12)
        error=(math.atan2(point[1]-s.y,point[0]-s.x)-s.heading+math.pi)%(2*math.pi)-math.pi
        steer=math.atan(2*session.sim.car.wheelbase*math.sin(error)/12)
        lock=session.sim.car.steer_lock/(1+(abs(s.vx)/P.steer_speed_scale)**2)
        session.step((steer/lock,max(-1,min(1,(16-s.vx)*.8))))
        assert session.sim.lap.valid
        if session.finished: break
    assert session.finished
    assert len(session.sim.lap.lap_times)==3
    loaded=PlayerSave(save.path)
    record=loaded.record(0,0)
    assert record and record['time']==min(session.sim.lap.lap_times)
    assert record['ghost'][0][0]==0
    assert record['ghost'][-1][0]==record['time']
    assert record['ghost'][-1][5]==session.sim.track.length
    ghost=Ghost(record)
    assert ghost.delta(record['time'],session.sim.track.length)==pytest.approx(0)
    before=asdict(session.sim.state)
    session.step((1,1))
    assert before==asdict(session.sim.state)


def test_menu_events_effects_and_render_read_only(tmp_path):
    os.environ['SDL_VIDEODRIVER']='dummy'; os.environ['SDL_AUDIODRIVER']='dummy'
    import pygame
    from gt_academy.game.client import Game
    from gt_academy.game.controls import analog
    game=Game(tmp_path/'save.json',window=(960,540))
    try:
        assert analog(.1)==0 and analog(1)==1 and analog(-1)==-1
        game.draw(.016)
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_RETURN))
        game.events()
        assert game.screen=='cars'
        for screen in ('cars','tracks','settings'):
            game.go(screen); game.draw(.016)
        game.rebinding='left'
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_j))
        game.events()
        assert game.settings['bindings']['left']==pygame.K_j
        game.mode='Free Practice'; game.start()
        before=asdict(game.session.sim.state)
        for quality in ('High','Medium','Low'):
            game.settings['quality']=quality; game.draw(.016)
        assert before==asdict(game.session.sim.state)
        pygame.event.post(pygame.event.Event(pygame.WINDOWFOCUSLOST))
        game.events(); assert game.screen=='pause'
        game.update(.1)
        assert before==asdict(game.session.sim.state)
        state=game.session.sim.state
        state.vx=20; state.slip_rear=.4; state.wall_contact=True; state.impact_speed=4
        for _ in range(200): game.renderer.effects_step(state,state,2)
        assert len(game.renderer.particles)<=35
        assert game.renderer.skids.get_bounding_rect().width>0
        game.audio.select_car(0); game.audio.update(state); game.audio.play('thump')
        for screen in ('pause','results'):
            game.go(screen); game.draw(.016)
    finally:
        game.audio.close(); pygame.quit()


def test_frozen_training_contract():
    assert SIM_VERSION=='f9dee10155f30db652ce63fd8e3e6cca5f233fc6e199a13f8bb2037eda30b824'
