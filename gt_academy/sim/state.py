"""Plain state containers; no clocks, random generators or display dependencies."""
from dataclasses import dataclass, field


@dataclass
class CarState:
    x: float = 0.0
    y: float = 0.0
    heading: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    yaw_rate: float = 0.0
    steering: float = 0.0
    throttle: float = 0.0
    brake: float = 0.0
    slip_front: float = 0.0
    slip_rear: float = 0.0
    force_front: float = 0.0
    force_rear: float = 0.0
    longitudinal_acceleration: float = 0.0
    lateral_acceleration: float = 0.0
    wheel_asphalt: tuple = (True, True, True, True)
    surface_front: str = 'asphalt'
    surface_rear: str = 'asphalt'
    wall_contact: bool = False
    impact_speed: float = 0.0
    index: int = 0
    offset: float = 0.0
    progress: float = 0.0
    ticks: int = 0


@dataclass
class LapState:
    previous_progress: float = 0.0
    previous_offset: float = 0.0
    next_gate: int = 1
    valid: bool = True
    elapsed: float = 0.0
    lap_times: list[float] = field(default_factory=list)
    best: float | None = None
    completed_this_step: bool = False
    invalid_reason: str = ''
    distance: float = 0.0
