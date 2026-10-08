import json
from pathlib import Path
from uuid import uuid4
from dataclasses import asdict
import pytest

pytestmark=pytest.mark.skipif(not Path('web/bridge.py').exists(),reason='Browser source is separate from desktop distribution')


def test_browser_practice_does_not_load_retained_trial_ghost_setting():
    from web.bridge import BrowserGame
    from gt_academy.game.session import Session
    from gt_academy.game.save import PlayerSave
    from gt_academy.sim.physics import approach
    from gt_academy.config import PHYSICS,VIEWER
    folder=Path('artifacts')/('browser_test_'+uuid4().hex[:8]);folder.mkdir(parents=True)
    game=BrowserGame(folder/'profile.json')
    game.start(json.dumps(dict(car=0,track=0,mode='Free Practice',aiGhost=True)))
    reference=Session(0,0,'Free Practice',PlayerSave(folder/'reference.json'))
    steer=0.
    for _ in range(60):
        game.step(.6,.7,1)
        steer=approach(steer,.6,VIEWER.keyboard_rate*PHYSICS.dt)
        reference.step((steer,.7))
    assert asdict(game.session.sim.state)==asdict(reference.sim.state)
    assert not hasattr(game.session,'opponent')


def test_browser_export_identity_and_version():
    from web.bridge import NumpyDriver
    if not Path('web/models/0-0-rookie.npz').exists():pytest.skip('Browser actors not installed')
    with pytest.raises(ValueError,match='identity'):NumpyDriver('web/models/0-0-rookie.npz',1,0)
    driver=NumpyDriver('web/models/0-0-rookie.npz',0,0)
    from gt_academy.sim import SIM_VERSION
    assert str(driver.data['sim_version'])==SIM_VERSION
