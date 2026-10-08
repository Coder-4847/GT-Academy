"""Five arcade car profiles; drag is calibrated analytically."""
from dataclasses import dataclass
from math import radians
from .config import PHYSICS


@dataclass(frozen=True)
class CarSpec:
    name: str
    archetype: str
    mass: float
    power_kw: float
    top_kph: float
    grip_front: float
    grip_rear: float
    brake_g: float
    steer_degrees: float
    launch_acceleration: float
    color: tuple
    wheelbase: float = 2.65
    front_weight: float = 0.48
    cg_height: float = 0.48
    hull_radius: float = 0.9
    hull_offset: float = 1.25

    @property
    def steer_lock(self) -> float:
        return radians(self.steer_degrees)

    @property
    def front_arm(self) -> float:
        return self.wheelbase * (1 - self.front_weight)

    @property
    def rear_arm(self) -> float:
        return self.wheelbase * self.front_weight

    @property
    def inertia(self) -> float:
        return self.mass * self.wheelbase ** 2 / 6

    @property
    def drag(self) -> float:
        speed = self.top_kph / 3.6
        rolling = PHYSICS.rolling * self.mass * PHYSICS.gravity
        return (self.power_kw * 1000 / speed - rolling) / speed ** 2


CARS = (
    CarSpec('Atlas', 'Balanced', 1200, 180, 230, 1.6, 1.6, 1.2, 32, 6.4, (216, 151, 100)),
    CarSpec('Bolt', 'Acceleration', 950, 190, 205, 1.5, 1.4, 1.1, 34, 8.0, (205, 184, 111)),
    CarSpec('Vector', 'Cornering grip', 1050, 160, 215, 1.9, 1.9, 1.4, 30, 6.0, (130, 176, 156)),
    CarSpec('Comet', 'Top speed', 1150, 260, 270, 1.4, 1.3, 1.0, 28, 6.8, (139, 164, 193)),
    CarSpec('Rogue', 'Agile / loose gravel', 1100, 220, 235, 1.6, 1.25, 1.1, 33, 7.4, (179, 138, 158)),
)
