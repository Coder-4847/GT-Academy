# Phase 2 report

**Latest revision:** the second driving review is implemented in [the arcade revision report](docs/ARCADE_REVISION.md): grippy asphalt handling, roughly 30% shorter 0–100 times, smoother presentation and graphics polish. Its 104-test result and simulation hash supersede the earlier handling results below. Training acceptance remains pending.

Phase 2 software is implemented, including the requested handling and track revisions. The user-run learning sanity test, laptop throughput/temperature checks and handling acceptance remain pending. No production training job was started. The historical Phase 1 report is preserved in `docs/PHASE_1_REPORT.md`.

## What changed and what was built

Steering responds sooner through a faster keyboard ramp, faster physical actuator response and slightly more steering authority at speed. Run-off has a progressive grip transition, milder drag and a small rear traction reserve. The original car specifications still meet their top-speed, acceleration and braking-order checks. A light road-edge touch retains more than 94% axle grip in the regression test. At 72 km/h, the steering-response check reaches meaningful steering and yaw within 150 ms.

Sunrise now includes a modest braking kink, Esses has stronger S-curves, and Longshot has two chicanes. Hairpin Valley and Grand Circuit retain their existing tighter technical layouts. The five-track roster and 25 model pairs remain intact. These are original tracks; the optional suggestion to copy F1 circuits was not needed.

The training pipeline now includes:

- Gymnasium environments using the same simulation and 32-float observations as the driving viewer, four physics ticks per action, seeded course-wide starts, episode termination/truncation and ordered-gate lap validation.
- Monotonic progress credit, time/impact/off-road/jerk costs and a speed-scaled valid-lap bonus. Reverse-and-forward movement and road re-entry cannot repeatedly claim the same progress.
- CPU-only PPO with two 256-unit tanh layers, VecNormalize, four DummyVecEnv environments per worker by default, one CPU/BLAS thread and configurable budgets/hyperparameters.
- Step-counted atomic checkpoint directories containing model/optimizer, normalization, metadata, file checksums and simulation hash. Incomplete saves are ignored; corrupted latest bundles can fall back to a complete earlier one. Incompatible simulation stamps are refused.
- Deterministic evaluation, a separate best-checkpoint pointer, per-run CSV/status logging, lap-history CSV and a matplotlib learning-curve tool. Evaluation preserves the training process's random-generator state.
- A Windows-safe launcher with car/track selection, a concurrency cap, below-normal priority, three crash retries, automatic resume, pre-flight information and graceful stop requests. An OS file lock prevents simultaneous writers. A unique worker token handles Windows venv redirector PID differences.
- User-run ten-minute sanity and 25-run throughput scripts with copyable summaries, CPU utilization sampling, wave recommendations, twelve-hour projections and temperature reminders.
- A read-only status monitor and separate 5×5 Training Wall. The wall plays saved policies slowly, loads one tile per frame, refreshes roughly every two minutes, and cannot stop training.
- `TRAINING_GUIDE.md`, updated README, interface documentation and recorded decisions.

## Exact commands

From PowerShell in the project folder, re-open the driving viewer to test the new code:

```powershell
Set-Location 'C:\Programming\Visual Studio Code\GT Academy'
.\launch.cmd
```

The installed environment is ready. On another machine, install Python 3.12/3.11 and run `setup.cmd` first.

Run the learning and hardware checks yourself, in this order:

```powershell
.\.venv\Scripts\python.exe -m tools.sanity_test
.\.venv\Scripts\python.exe -m tools.benchmark_25
```

Each defaults to approximately ten minutes plus startup/evaluation. The second starts 25 workers; lower concurrency uses multiple ten-minute waves. Paste the final summary blocks if sanity fails or throughput is poor. These scripts use separate experiment folders and do not freeze production physics.

After those checks and driving feedback pass, the intended overnight command is:

```powershell
.\.venv\Scripts\python.exe -m tools.train_all --hours 12 --max-concurrent 25 --n-envs 4
```

Use the concurrency established by your benchmark. The budget is per driver: up to twelve lifetime active hours or 20 million lifetime environment steps. With twelve workers, three waves can take up to 36 wall-clock hours. Reserve about 12 GiB for default checkpoints/logs plus dependencies. Read `TRAINING_GUIDE.md` for the full setup, power/sleep checklist, monitoring commands, safe stopping and recovery.

## Actual verification results

Verified on Python 3.12.14, NumPy 2.5.3, pygame-ce 2.5.8, CPU PyTorch 2.8.0, Stable-Baselines3 2.9.0, Gymnasium 1.3.0 and pytest 9.1.1. These were developer bug checks, not user hardware/learning acceptance runs.

```text
python -m pytest -q -p no:cacheprovider
........................................................................ [ 94%]
....                                                                     [100%]
76 passed in 4.50s

python -m pip check
No broken requirements found.
```

The 76 tests cover the original physics/track/sensor/lap guarantees plus all 25 Gymnasium car/track pairs, environment API compatibility, seeded resets, termination versus truncation, progress-reward exploit rejection, the handling regressions, exact normalized-policy loading parity, frozen inference statistics, optimizer/normalization resume, checksum recovery, writer/freeze locks, stop requests, concurrency/restart behavior, Windows redirector status identification and preservation of training RNG during evaluation.

Actual subprocess checks also passed:

```text
One PPO worker: saved at 32 steps; resumed to 48 steps.
Graceful stop request: final checkpoint saved at 64 steps; status stopped.
Two-worker launcher: Atlas + Bolt, each 32 steps; 0 failed.
Actual launcher/worker tokens agree across Windows redirector PIDs.
```

The real-worker stop test uses the same stop-file mechanism triggered by launcher Ctrl+C; physical keyboard Ctrl+C delivery was not manually exercised. Crash/restart scheduling was exercised with simulated worker exits in the unit suite. The forced-termination fallback is implemented but was not used as an acceptance test against a deliberately hung production process.

All 25 car/track combinations passed offscreen debug-viewer drawing and input checks. Track overview images were inspected. The Training Wall loaded a real saved test policy, showed waiting tiles for missing models and rendered successfully offscreen. Those policies received only bug-check training and are not race-ready. The small deterministic policy evaluation correctly reported no completed lap after such a tiny training budget.

The short single-process simulation benchmark reported:

```text
python -m tools.benchmark --steps 1000 --bug-check
Physics only              2,000 sim steps/s (0.500 ms/step)
Physics + observation     1,890 sim steps/s (0.529 ms/step)
Backend: Python + NumPy; Numba is not used.
```

These are **simulation ticks**, not PPO environment steps or concurrent training throughput. Each policy action normally advances four ticks. The values do not establish the 1,500 environment-step/s training target. No ten-minute sanity test, 25-run benchmark or overnight job was run by the developer.

The calibrated free-asphalt top speeds remain 230/205/215/270/235 km/h to within 0.001 km/h in the bug check. Bolt remains quickest to 100 km/h at 3.867 s; Vector has the shortest 150 km/h stop at 66.814 m and Comet the longest at 87.196 m. These are simulation calibration results, not real-car performance claims.

## Decisions, assumptions and limitations

Full rationale is in `DECISIONS.md`. The user explicitly authorized the handling/track changes and Phase 2. Physics was revised before any real training freeze. The observation layout stayed at 32 floats; environment/reward behavior and action frequency were added to the hash.

The best model is retained by a separate pointer to its immutable, complete checkpoint bundle. All checkpoints are kept for future tier selection. Resuming restores optimizer and normalization but restarts episodes; it is not an exact replay of an interrupted random trajectory. Default time/step budgets are lifetime per run and must be increased for additional training after completion.

Still awaiting user evidence:

- The revised steering and road-edge recovery feel right in play.
- Atlas completes evaluated Sunrise laps after the ten-minute sanity run.
- All 25 workers sustain useful throughput and acceptable temperatures on the laptop; the 1,500 environment-step/s target is not certified. Numba or further hot-path work may be needed after profiling.
- The Training Wall's overhead with 25 loaded models is small enough during actual training.
- Long-duration recovery/stability and all drivers' eventual lap completion are established.

The 6–12% best-lap balance target needs strong drivers and remains unverified. Final game menus, gamepad controls, audio, effects, ghosts, racing modes, career, tier extraction and final packaging belong to Phases 3–5.

## Physics freeze

Current simulation contract:

```text
c031509107bd525e7f1cca11b7ddee0e02adc0b3bc7c6536266ec37136ee048e
```

It covers physics, cars, tracks, collision/lap behavior, observations/actions, the environment, frame skip and reward. Renderer settings and optimizer hyperparameters are outside the stamp. Existing Phase 1 stamps differ intentionally because the user requested physics changes.

No production physics lock was created by these checks. The first real `train_all` run writes `runs/physics_lock.json`. From that point, changes to the contract require deliberate retraining. Finish driving, sanity and benchmark review before that launch.

The environment/normalization integration follows the official [Gymnasium environment API](https://gymnasium.farama.org/introduction/create_custom_env/) and [Stable-Baselines3 VecNormalize guidance](https://stable-baselines3.readthedocs.io/en/master/guide/vec_envs.html#vecnormalize).
