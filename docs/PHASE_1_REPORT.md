# Phase 1 report

Implementation and automated verification are complete. Human driving acceptance is still pending, as required by the master plan. This report covers Phase 1 only.

## What was built

- Five specified car archetypes with their original mass, power, top-speed, grip, braking and steering-lock values.
- Deterministic single-track tire physics, smooth post-peak slide forces, combined longitudinal/lateral grip, longitudinal load transfer, rear-wheel drive, drag, rolling resistance and low-speed blending.
- Shared speed-sensitive steering, steering-rate limits and throttle/brake slew limits.
- Five original closed spline tracks with 1 m geometry, surfaces, inside-corner kerbs, run-off, walls, start positions and import-time validation.
- Per-wheel surface sampling, a three-circle collision hull and wall response at three substeps per 60 Hz tick.
- Ordered forward checkpoint gates, invalid-lap handling, lap times and best lap.
- Eleven edge-distance rays and the complete 32-value normalised observation builder.
- Simulation content hash and mismatch rejection API.
- Pygame debug viewer with keyboard driving, car/track switching, telemetry, map/follow views, force/slip/hull overlays, rays, pause, reset, resizing and fullscreen.
- Windows setup/launch scripts, readable source, interface documentation, calibration tools and the test suite.

## Exact commands

The local environment is already installed. Open PowerShell:

```powershell
Set-Location 'C:\Programming\Visual Studio Code\GT Academy'
.\launch.cmd
```

The driving window should appear within a few seconds. Drive with WASD/arrows, select cars with 1–5, switch tracks with T, and reset with R. H toggles track-relative telemetry. The README lists all controls and explains clean laps.

Run verification and the user-side benchmark:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m tools.validate_physics
.\.venv\Scripts\python.exe -m tools.benchmark --steps 10000
```

Allow several seconds for tests/calibration and tens of seconds for the benchmark. Expect all tests to pass and two steps/s lines. Paste the failure text if a test fails. For a fresh installation, run `setup.cmd` first after installing Python 3.12 or 3.11.

## Actual test and benchmark results

Verification used Python 3.12.14, NumPy 2.5.3, pygame-ce 2.5.8 and pytest 9.1.1 on 3 October 2026.

```text
python -m pytest -q -p no:cacheprovider
...................................... [100%]
38 passed in 3.29s
```

The cache plugin was disabled because the agent sandbox blocked pytest's cache-directory rename on an earlier run. This changes no simulation tests.

The suite covers exact deterministic trajectories, rest stability, all five top speeds, launch/braking order, tire saturation and combined grip, skidpad response including Rogue's rear slip, valid tracks and local/global/batched nearest queries, top-speed wall impacts on every track in both directions, ordered laps, reverse/shortcut rejection, a complete lap through the actual physics, bounded pure observations, ray agreement with a full-edge search, actuator slew, grass detection, invalid inputs, hash mismatches and a pygame-free core import.

`tools.verify_viewer` passed all **25 car/track combinations** and selection/toggle event checks. The five track overview renders and the follow-camera view were visually inspected. This was an offscreen bug check, not a display-FPS measurement.

| Car | Measured top speed | 0–100 km/h | Stop from 150 km/h | Peak lateral load |
| --- | ---: | ---: | ---: | ---: |
| Atlas | 229.999 km/h | 4.783 s | 75.285 m | 1.448 g |
| Bolt | 205.000 km/h | 3.867 s | 78.608 m | 1.333 g |
| Vector | 215.000 km/h | 5.083 s | 66.814 m | 1.671 g |
| Comet | 270.000 km/h | 4.433 s | 87.196 m | 1.258 g |
| Rogue | 235.000 km/h | 4.100 s | 82.942 m | 1.279 g |

Top speed is measured on unrestricted asphalt after 120 simulated seconds. Braking includes actuator buildup. The skidpad test gradually increases steering with a speed controller; values are peaks in that dynamic maneuver, not constant-radius sustained lap claims. At Rogue's peak load, front slip is 10.85° and rear slip is 12.61°.

The last short benchmark was explicitly a **bug check only**:

```text
python -m tools.benchmark --steps 2000 --bug-check
Physics only              1,112 sim steps/s (0.899 ms/step)
Physics + observation       837 sim steps/s (1.195 ms/step)
Backend: Python + NumPy; Numba is not used.
```

These numbers describe this short verification workload. They do not certify laptop temperature, sustained speed, concurrent PPO throughput or the Phase 2 target of 1,500 environment steps/s per training process. The workload includes off-road/wall driving and periodic resets. Run the supplied benchmark yourself and retain its output before Phase 2 optimization.

## Decisions and assumptions

The project follows the document's one-phase-at-a-time rule. Physics uses SI units, fixed substeps and common driver inputs. Tracks use closed cubic B-splines, grass provides run-off handling, forward-only pedal control is intentional, and leaving the course invalidates a lap. Observation layout and version coverage are explicitly documented. The existing workspace serves as the project root. Full rationale is in `DECISIONS.md`.

## Known limitations and remaining acceptance

- Drive all five cars and tracks to assess handling, drift recovery, keyboard feel and collision feel. Automated tests cannot certify those subjective qualities.
- The 6–12% fastest-to-slowest best-lap balance target and differing car rankings are unverified; they require strong drivers and later training results.
- This is the Phase 1 debug viewer. Final car art, audio, effects, menus, ghosting, gamepad controls, trained opponents, difficulty tiers and career progression belong to later phases.
- The geometric test driver is used only inside a unit test. No scripted opponent is presented as trained AI.
- RL dependencies, rewards, checkpoint serialization, launcher recovery and training tools are not part of this phase. No training has run.
- Display FPS, laptop thermals and long-running stability still require the user's hardware checks. Only the offscreen renderer and short simulation workloads were exercised here.

## Physics freeze

The current simulation stamp is:

```text
d14b0043fba3bf5e72cfbcdfdf3ec29ad07c0fb4b4a12f5b380132bfcb35bbb2
```

It prints in full on viewer launch; the footer shows its first 12 characters. The core exposes `require_version()` to reject incompatible model metadata. Phase 2 will store this stamp with every model and its normalization data, and add the reward definition before the freeze.

**Physics is not frozen and real training has not started.** Resolve driving feedback first. After Phase 2 sanity testing and the user's benchmark pass, freeze physics, geometry, observations, actions and rewards before the user starts the overnight run.
