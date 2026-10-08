"""Presentation-only defaults. Nothing here changes the frozen simulation."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ClientConfig:
    window: tuple = (1920,1080)
    canvas: tuple = (1440,810)
    fps: int = 60
    countdown: float = 3.0
    trial_laps: int = 3
    camera_response: float = 5.0
    lookahead: float = .35
    zoom: float = 9.0
    zoom_speed: float = 170.0
    transition: float = .18
    deadzone: float = .14
    analog_curve: float = 1.35
    assist_yaw: float = .10
    ghost_stride: int = 2
    max_ghost_samples: int = 54000
    quality_scales: tuple = (1.0,.8,.6667)
    particle_limits: tuple = (180,90,35)
    slip_threshold: float = .12
    smoke_threshold: float = .22
    particle_lifetime: float = .8
    shake_seconds: float = .18
    audio_rate: int = 22050
    impact_interval_ms: int = 150
    replay_seconds: float = 12.
    replay_stride: int = 2
    background: tuple = (15,23,30)
    panel: tuple = (25,36,45)
    foreground: tuple = (234,238,232)
    muted: tuple = (147,164,173)
    accent: tuple = (147,216,181)


CLIENT = ClientConfig()
DEFAULT_SETTINGS = {'quality':'High','master':.65,'engine':.55,'effects':.65,
                    'mute':False,'assist':False,'fullscreen':False,
                    'ai_noise':0.,'ai_penalty':0.,'race_laps':3,'rival_car':0,'rival_tier':'Rookie','ai_ghost':False,
                    'bindings':{'throttle':119,'brake':115,'left':97,'right':100,'reset':114}}
