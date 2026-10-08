"""Monotonic progress credit prevents reverse-and-forward reward farming."""
from dataclasses import dataclass
from ..config import REWARD as R


@dataclass
class ProgressCredit:
    distance: float = 0.
    high_water: float = 0.

    def advance(self, delta: float, eligible: bool) -> float:
        self.distance += delta
        fresh = max(0.,self.distance-self.high_water)
        # Off-course distance is consumed, never banked for later re-entry.
        self.high_water = max(self.high_water,self.distance)
        return fresh if eligible else 0.


def driving_reward(progress: float, seconds: float, offroad: float,
                   impact: float, jerk: float, lap_time: float | None,
                   reference_time: float) -> float:
    value = R.progress*progress - R.time_cost*seconds
    value -= R.offroad*offroad*seconds + R.impact*impact + R.action_change*jerk
    if lap_time is not None:
        value += R.lap_bonus*(1+min(2.,reference_time/max(lap_time,1.)))
    return float(value)
