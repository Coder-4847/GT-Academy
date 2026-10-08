"""Shared parameters. SI units throughout: metres, seconds, radians, newtons."""
from dataclasses import dataclass


@dataclass(frozen=True)
class PhysicsConfig:
    dt: float = 1 / 60
    substeps: int = 3
    gravity: float = 9.81
    rolling: float = 0.013
    power_speed_floor: float = 8.0
    steer_rate: float = 8.0
    steer_response: float = 55.0
    acceleration_gain: float = 1.4
    arcade_yaw_response: float = 24.0
    arcade_cornering_gain: float = 2.6
    arcade_lateral_response: float = 30.0
    steer_speed_scale: float = 30.0
    throttle_slew: float = 8.0
    brake_slew: float = 5.0
    brake_bias: float = 0.58
    kinetic_blend_start: float = 1.0
    kinetic_blend_end: float = 5.0
    tire_shape: float = 1.4
    tire_curvature: float = -0.15
    front_stiffness: float = 13.0
    rear_stiffness: float = 14.0
    slip_speed_floor: float = 2.0
    grass_grip: float = 0.72
    kerb_grip: float = 0.95
    grass_drag: float = 0.18
    edge_blend_width: float = 1.6
    drive_grip_fraction: float = 0.95
    offroad_drive_reserve: float = 0.1
    restitution: float = 0.1
    wall_friction: float = 0.12
    max_yaw_kick: float = 0.7
    contact_iterations: int = 3
    rest_speed: float = 0.035
    max_load_transfer: float = 0.35


@dataclass(frozen=True)
class TrackConfig:
    spacing: float = 1.0
    spline_samples: int = 80
    nearest_window: int = 16
    runoff: float = 6.0
    kerb_width: float = 0.8
    kerb_curvature: float = 0.009
    gates: int = 12
    max_progress_step: float = 4.0
    length_tolerance: float = 0.1
    validation_stride: int = 5
    grid_spacing: float = 7.0


@dataclass(frozen=True)
class SensorConfig:
    rays: int = 11
    spread_degrees: float = 100.0
    ray_range: float = 70.0
    ray_window: int = 100
    speed_scale: float = 85.0
    lateral_speed_scale: float = 25.0
    yaw_scale: float = 2.5
    slip_scale: float = 0.8
    curvature_scale: float = 0.05
    lookahead: tuple = (10.0, 20.0, 40.0, 70.0)
    straight_range: float = 300.0
    straight_curvature: float = 0.004


@dataclass(frozen=True)
class ViewerConfig:
    width: int = 1440
    height: int = 900
    fps: int = 120
    pixels_per_metre: float = 9.0
    camera_response: float = 5.0
    keyboard_rate: float = 20.0
    force_scale: float = 0.002
    background: tuple = (22, 27, 30)
    panel: tuple = (30, 36, 39)
    text: tuple = (231, 234, 230)
    secondary: tuple = (156, 170, 169)


PHYSICS = PhysicsConfig()
TRACK = TrackConfig()
SENSORS = SensorConfig()
VIEWER = ViewerConfig()


@dataclass(frozen=True)
class EnvironmentConfig:
    frame_skip: int = 4
    reference_speed: float = 24.0
    time_limit_multiplier: float = 2.5
    max_laps: int = 1
    serious_impact: float = 10.0
    offroad_timeout: float = 2.0
    stalled_timeout: float = 8.0
    backward_limit: float = 8.0
    start_offset: float = 0.6
    start_heading: float = 0.07
    start_speed: float = 8.0
    grid_start_probability: float = 0.35
    evaluation_starts: tuple = ((0.,0.),(0.3,0.02),(-0.3,-0.02))


@dataclass(frozen=True)
class RewardConfig:
    progress: float = 1.0
    time_cost: float = 0.5
    lap_bonus: float = 50.0
    impact: float = 0.8
    offroad: float = 4.0
    action_change: float = 0.03


@dataclass(frozen=True)
class TrainingConfig:
    n_envs: int = 4
    hidden_layers: tuple = (256,256)
    rollout_steps: int = 1024
    batch_size: int = 256
    epochs: int = 10
    gamma: float = 0.995
    gae_lambda: float = 0.95
    learning_rate: float = 3e-4
    final_learning_rate: float = 5e-5
    entropy: float = 0.005
    clip_range: float = 0.2
    checkpoint_steps: int = 250_000
    evaluate_every: int = 4
    evaluation_episodes: int = 3
    total_steps: int = 20_000_000
    hours: float = 12.0
    max_concurrent: int = 25
    restart_limit: int = 3
    status_seconds: float = 5.0
    monitor_seconds: float = 5.0
    stalled_lap_steps: int = 1_000_000
    stop_grace_seconds: float = 120.0
    seed: int = 42
    wall_fps: int = 6
    wall_reload_seconds: float = 120.0
    wall_width: int = 1500
    wall_height: int = 1000
    target_env_steps_per_second: float = 1500.0


ENVIRONMENT = EnvironmentConfig()
REWARD = RewardConfig()
TRAINING = TrainingConfig()
