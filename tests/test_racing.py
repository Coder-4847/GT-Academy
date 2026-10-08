"""Tier and race rules; disposable outputs, no production training writes."""
from dataclasses import asdict
import json
from pathlib import Path
from uuid import uuid4
import numpy as np
import pytest
from gt_academy.game.racing import Opponent,RaceSession,AIGhostSession,unlocked,OpponentLibrary
from gt_academy.game.save import PlayerSave
from gt_academy.rl.tiers import choose_tiers,unpack_bundle,outside_runs
from gt_academy.sim import Simulation,observation
from gt_academy.cars import CARS
from gt_academy.tracks import TRACKS
from gt_academy.config import ENVIRONMENT as E


@pytest.fixture
def folder():
    path=Path('artifacts')/f'race_test_{uuid4().hex[:10]}'
    path.mkdir(parents=True)
    return path


class FakeDriver:
    def __init__(self): self.calls=0; self.closed=False
    def action(self,obs): self.calls+=1; return np.array((.1,.6),dtype=np.float32)
    def close(self): self.closed=True


def test_tier_order_reliability_and_warnings():
    def row(time,rate=1,episodes=3):
        return {'mean_lap':time,'checkpoint':str(time),'completion_rate':rate,'episodes':episodes}
    selected,warnings=choose_tiers([row(100),row(103),row(112),row(135),row(144),row(80,.67),row(70,1,1)])
    assert [r['mean_lap'] for r in selected.values()]==[144,112,103,100]
    selected,warnings=choose_tiers([row(100)])
    assert len(warnings)>0 and len(selected)==4
    with pytest.raises(ValueError): choose_tiers([row(90,.67)])


def test_career_sequence_save_and_legend(folder):
    save=PlayerSave(folder/'profile.json')
    assert unlocked(save.medals,0,'Rookie')
    assert not unlocked(save.medals,1,'Rookie')
    assert not save.award(0,'Champion',30)
    for track in range(5):
        for tier in ('Rookie','Pro','Champion'):
            assert save.award(track,tier,50)
    assert all(unlocked(save.medals,t,'Legend') for t in range(5))
    assert PlayerSave(save.path).medals==save.medals
    assert not save.award(0,'Legend',-3)


def test_opponent_cadence_and_same_physics():
    driver=FakeDriver(); opponent=Opponent(driver,0,0)
    reference=Simulation(CARS[0],TRACKS[0])
    for _ in range(20):
        opponent.step(); reference.step((float(np.float32(.1)),float(np.float32(.6))))
        assert asdict(opponent.sim.state)==asdict(reference.state)
    assert driver.calls==20//E.frame_skip


def test_noise_disabled_deterministic_and_delay():
    a,b=Opponent(FakeDriver(),0,0),Opponent(FakeDriver(),0,0,imperfection=1)
    a.step(); b.step()
    assert a.sim.state.throttle>0 and b.sim.state.throttle==0
    for _ in range(12): b.step()
    assert b.sim.state.throttle>0


def finish_fixture(race,player_time,ai_time):
    race.countdown=0
    race.elapsed=player_time-1/60
    race.opponent.finish_time=ai_time
    def step(action):
        race.sim.lap.completed_this_step=True
        race.sim.lap.lap_times=[player_time/race.laps]*race.laps
        race.sim.lap.elapsed=0
    race.sim.step=step
    race.step((0,0))


def test_penalty_results_and_custom_race_no_medal(folder):
    save=PlayerSave(folder/'save.json')
    race=RaceSession(0,0,'Race vs AI',save,FakeDriver(),1,'Rookie',1,penalty=5)
    finish_fixture(race,32,30)
    assert race.result=='Victory' and race.finished
    assert save.medals=={}
    assert PlayerSave(save.path).race_bests['0:0:1']==pytest.approx(32)
    loss=RaceSession(0,0,'Race vs AI',save,FakeDriver(),1,'Rookie',1)
    finish_fixture(loss,32,30)
    assert loss.result=='Defeat'


def test_career_has_no_handicap_and_awards_only_finished_win(folder):
    save=PlayerSave(folder/'save.json')
    race=RaceSession(0,0,'Career',save,FakeDriver(),1,'Rookie',1,60,1)
    assert race.laps==3 and race.penalty==0 and race.opponent.imperfection==0
    assert not race.reset_to_track()
    assert save.medals=={}
    finish_fixture(race,80,90)
    assert race.result=='Victory' and '0:Rookie' in save.medals
    race.close(); assert race.opponent.driver.closed


def test_race_countdown_and_noncollision(folder):
    save=PlayerSave(folder/'save.json')
    race=RaceSession(0,0,'Race vs AI',save,FakeDriver(),0,'Rookie')
    before=asdict(race.sim.state)
    for _ in range(180): race.step((1,1))
    assert before==asdict(race.sim.state)==asdict(race.opponent.sim.state)
    race.step((0,0))
    assert race.sim.state.vx==0 and race.opponent.sim.state.vx>0


def test_gap_uses_common_progress_time(folder):
    race=RaceSession(0,0,'Race vs AI',PlayerSave(folder/'save.json'),FakeDriver(),1,'Rookie',penalty=3)
    race.history=[[(0,0),(100,10)],[(0,0),(100,12)]]
    assert race.gap==pytest.approx(-5)


def test_output_protection_and_missing_library(folder):
    with pytest.raises(ValueError): outside_runs(Path('runs')/'new.json')
    with pytest.raises(ValueError,match='unavailable'): OpponentLibrary(folder).load(0,0,'Rookie')


def test_export_version_rejection_before_loading(folder):
    import zipfile
    bundle=folder/'wrong.zip'
    with zipfile.ZipFile(bundle,'w') as archive:
        for name in ('model.zip','vecnormalize.pkl','stats.json'): archive.writestr(name,'x')
        archive.writestr('metadata.json',json.dumps({'sim_version':'wrong'}))
    with pytest.raises(ValueError,match='Simulation mismatch'):
        unpack_bundle(bundle,folder/'cache',0,0)
