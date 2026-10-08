"""Shared inference loader: weights and frozen VecNormalize stats are inseparable."""
from pathlib import Path
import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
from .env import RacingEnv
from .storage import validate_checkpoint


class Driver:
    def __init__(self, checkpoint: Path, car_id: int | None = None, track_id: int | None = None):
        self.metadata=validate_checkpoint(checkpoint,car_id,track_id)
        self.car_id=self.metadata['car_id']; self.track_id=self.metadata['track_id']
        base=DummyVecEnv([lambda:RacingEnv(self.car_id,self.track_id,training=False)])
        self.normalizer=VecNormalize.load(checkpoint/'vecnormalize.pkl',base)
        self.normalizer.training=False
        self.normalizer.norm_reward=False
        self.model=PPO.load(checkpoint/'model.zip',device='cpu')

    def action(self, raw_observation: np.ndarray) -> np.ndarray:
        normalized=self.normalizer.normalize_obs(raw_observation.reshape(1,-1))
        action,_=self.model.predict(normalized,deterministic=True)
        return action[0]

    def close(self) -> None:
        self.normalizer.close()
