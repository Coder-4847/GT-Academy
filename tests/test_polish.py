"""Replay isolation, real input events and damaged-file recovery."""
from dataclasses import asdict
import json
import os
from pathlib import Path
from uuid import uuid4
import pytest
from gt_academy.game.replay import Replay
from gt_academy.game.save import PlayerSave
from gt_academy.game.session import Session
from gt_academy.game.racing import OpponentLibrary
from gt_academy.sim import SIM_VERSION


@pytest.fixture
def folder():
    path=Path('artifacts')/('polish_test_'+uuid4().hex[:10])
    path.mkdir(parents=True)
    return path


def test_replay_bounded_and_never_mutates_live_session(folder):
    session=Session(0,0,'Free Practice',PlayerSave(folder/'save.json'))
    session.countdown=0
    replay=Replay(seconds=2)
    for _ in range(240):
        session.step((0,.5)); replay.record(session)
    assert len(replay.frames)==61 and replay.duration==2
    before=asdict(session.sim.state)
    replay.start(); replay.update(.125)
    state,_=replay.at()
    assert replay.frames[3][0].x<=state.x<=replay.frames[4][0].x or replay.frames[4][0].x<=state.x<=replay.frames[3][0].x
    state.x=9999
    assert replay.frames[3][0].x!=9999
    replay.paused=True; replay.update(1); assert replay.playhead==.125
    replay.paused=False; assert replay.update(5)
    assert replay.playhead==2 and asdict(session.sim.state)==before


@pytest.mark.parametrize('data',[[],None,{'settings':[]},{'records':{'x':None},'sim_version':SIM_VERSION}])
def test_malformed_save_shapes_remain_playable(folder,data):
    path=folder/'save.json'; path.write_text(json.dumps(data))
    save=PlayerSave(path)
    assert save.settings['quality']=='High' and save.records=={}
    assert save.flush()


@pytest.mark.parametrize('data',[[],{'sim_version':SIM_VERSION,'pairs':[]},{'sim_version':'incompatible'}])
def test_bad_manifest_reports_clear_error(folder,data):
    (folder/'manifest.json').write_text(json.dumps(data))
    with pytest.raises(ValueError): OpponentLibrary(folder).stats(0,0,'Rookie')


def test_corrupt_zip_rejected_without_crash(folder):
    from gt_academy.rl.storage import file_hash
    bundle=folder/'bad.zip'; bundle.write_bytes(b'bad archive')
    (folder/'manifest.json').write_text(json.dumps({'sim_version':SIM_VERSION,'pairs':{'0:0':{'Rookie':{'bundle':'bad.zip','sha256':file_hash(bundle),'mean_lap':30,'completion_rate':1}}}}))
    with pytest.raises(ValueError,match='corrupt'): OpponentLibrary(folder).load(0,0,'Rookie')


def test_window_focus_controller_replay_photo_and_resize(folder,monkeypatch):
    os.environ['SDL_VIDEODRIVER']='dummy'; os.environ['SDL_AUDIODRIVER']='dummy'
    import pygame
    from gt_academy.game.client import Game
    game=Game(folder/'save.json',window=(960,540))
    try:
        game.mode='Free Practice'; game.start(); game.session.countdown=0
        game.controls.action=lambda state:(0,.4)
        for _ in range(120): game.update(1/60)
        before=asdict(game.session.sim.state)
        pygame.event.post(pygame.event.Event(pygame.WINDOWFOCUSLOST))
        game.events(); assert game.screen=='pause'
        game.update(1); assert asdict(game.session.sim.state)==before
        game.go('drive')
        pygame.event.post(pygame.event.Event(pygame.CONTROLLERDEVICEREMOVED,which=0))
        game.events(); assert game.screen=='pause'
        pygame.event.post(pygame.event.Event(pygame.VIDEORESIZE,w=1100,h=650))
        game.events(); assert game.display.get_size()==(1100,650)
        game.start_replay(); assert game.screen=='replay'
        game.draw(1/60); game.update(.2)
        assert asdict(game.session.sim.state)==before
        saved=[]
        monkeypatch.setattr(pygame.image,'save',lambda surface,path:saved.append((surface.get_size(),path)))
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_F12))
        game.events(); game.draw(0)
        assert saved and saved[0][0]==(1440,810) and saved[0][1].endswith('.png')
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_SPACE))
        game.events(); assert game.replay.paused
        game.back(); assert game.screen=='results'
    finally: game.audio.close(); pygame.quit()
