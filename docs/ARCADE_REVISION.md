# Arcade handling and presentation revision — 3 October 2026

## Follow-up: steering authority

The next driving review found turning still too stiff. The asphalt cornering cap now has a 2.6 multiplier, fading to the original tire budget on full gravel. This changes turning authority only; acceleration, braking, steering response, gravel tire parameters and rendering are unchanged. Constant-speed Atlas full-steer radius at 100 km/h falls from 49.1 m to 18.9 m (about 62% tighter). At 72 km/h it falls from 25.5 m to 9.8 m. All five cars pass tighter-radius checks at 72, 126 and 198 km/h, alongside the existing spin/recovery checks. **119 tests passed.**

Current simulation hash: `f9dee10155f30db652ce63fd8e3e6cca5f233fc6e199a13f8bb2037eda30b824`. The previous revision and its measurements below are historical; older policies require retraining.

## Previous revision

The user's second driving review supersedes the original drift-heavy road handling. All five cars now use fast, stabilized asphalt steering; tire dynamics progressively take over in gravel. Throttle no longer consumes asphalt cornering authority. Too much speed produces a wider turn rather than a rear-grip snap. People and policies use the same simulation.

Steering rate increases from 3.2 to 8 radians/second, response from 22 to 55, and the keyboard ramp from 7 to 20 units/second. All five cars exceed 0.45 rad/s yaw response within 100 ms at an initial 72 km/h. Assistance retains the existing 1.6 m progressive edge transition. Rogue remains more loose on gravel but is no longer intentionally unstable on asphalt.

Propulsion increases by 40%, with faster throttle response and shared road traction. Aerodynamic and rolling resistance are scaled to retain the original top speeds. This exceeds the requested 25% acceleration improvement in the measured launch check:

| Car | Previous 0–100 km/h | Revised | Time reduction | Top speed |
| --- | ---: | ---: | ---: | ---: |
| Atlas | 4.783 s | 3.350 s | 30.0% | 230 km/h |
| Bolt | 3.867 s | 2.700 s | 30.2% | 205 km/h |
| Vector | 5.083 s | 3.567 s | 29.8% | 215 km/h |
| Comet | 4.433 s | 3.100 s | 30.1% | 270 km/h |
| Rogue | 4.100 s | 2.867 s | 30.1% | 235 km/h |

Rendering interpolates position, heading and steering between fixed simulation ticks, uses a high-resolution presentation clock, and applies time-based camera/zoom smoothing. Correcting the fractional map-crop offset removes coarse map-pixel camera snapping. The viewer targets 120 FPS; physics remains deterministic at 60 Hz with three substeps. Pausing and resetting clear interpolation history.

The graphics pass adds a wider driving view, speed/lap HUD, minimap, throttle/brake indicator, red-and-white kerbs, road/terrain grain, trees with shadows, brighter barriers, and headlights/roof/bonnet/wing detail. Debug rays and forces are optional; Tab opens telemetry. This is a procedural 2D polish pass; future game presentation work remains.

Validation: 104 tests passed, including all-car launch comparisons, sharp alternating steering under throttle and braking at three speeds, release recovery, gravel-versus-edge behavior, heading interpolation across the angle wrap, render-state immutability, and existing simulation/RL checks. The offscreen viewer passed all 25 car/track combinations and input event checks. The actual viewer loop passed a 30-frame smoke check. A 240-frame offscreen workload measured 2.713 ms median / 3.200 ms p95 in this environment; this excludes display synchronization and does not guarantee live FPS or replace the user's driving assessment.

Current simulation hash: `ccd22a8b497f1d1d0b879a12f1d60b90b995f76fe78a31f62382b41e3f75cca1`. Older policies require retraining. No production training was launched and no prior checkpoints were deleted. The ten-minute learning check and sustained laptop benchmark remain user-run steps.
