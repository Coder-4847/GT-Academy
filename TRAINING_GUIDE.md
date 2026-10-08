# Train the GT Academy drivers

**Status, 7 October 2026:** all 25 production runs are complete on the frozen arcade simulation. Phases 3–5 are implemented without retraining. Preserve `runs/`; the instructions below are reference for future training you choose to run. The diagnostic viewer is now launched with `.\.venv\Scripts\python.exe -m tools.debug_drive`; `launch.cmd` opens the complete game client.

The training tools remain available for future work you choose to run. Existing trained drivers are exported and ready to race. You run any new training yourself; do not rerun these training steps simply to play the game.

## What is happening

Each driver learns by trying steering, throttle and braking inputs thousands of times. It earns reward for new forward progress and clean laps, and loses reward for impacts, leaving the road, wasting time and jerky inputs. Reversing and driving over the same patch again cannot earn repeated progress reward. There is one separate driver for each of the five cars on each of the five tracks: 25 drivers.

A checkpoint is a saved driver. Its folder includes the neural-network weights, observation/reward normalization statistics, optimizer state and a simulation hash. Keep the complete folder together; the normalization state is needed alongside the model, as described in the [Stable-Baselines3 guide](https://stable-baselines3.readthedocs.io/en/master/guide/vec_envs.html#vecnormalize). Training uses the CPU and runs without an open chat; it consumes no chat tokens.

## One-time setup

On this machine, open PowerShell and run:

```powershell
Set-Location 'C:\Programming\Visual Studio Code\GT Academy'
.\setup.cmd
```

Setup reuses the prepared Python 3.12 environment, installs any missing dependencies and runs the tests. Expect `149 passed` and `Ready. Run launch.cmd to drive.` The first dependency download on a fresh machine can take several minutes; CPU PyTorch alone downloads about 620 MB and uses more space when installed.

On another Windows machine, install Python 3.12 with its launcher first. The equivalent manual setup is:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

No virtual-environment activation is needed. If pytest reports only a cache permission warning, rerun with `-p no:cacheprovider`.

## Step 1 — drive the revised handling

```powershell
.\launch.cmd
```

Steering now responds sooner; the edge gradually reduces grip instead of suddenly adding heavy drag. Sunrise has a braking kink, Esses has stronger direction changes, and Longshot has two chicanes. The five original tracks remain the 25-model roster.

Choose a car and track through the menus, then use WASD/arrows and R to reset. The separate `tools.debug_drive` laboratory retains 1–5 for cars and T for tracks. Try a small road-edge touch and recovery. Confirm you like the handling before spending time training. Further physics changes invalidate existing models.

## Step 2 — the ten-minute sanity test

```powershell
.\.venv\Scripts\python.exe -m tools.sanity_test
```

This trains Atlas on Sunrise for approximately ten minutes, then evaluates it from three reproducible grid variants. Allow extra time for startup and evaluation. It uses a new folder under `experiments`, prints its path at startup, and does not freeze physics or overwrite real runs.

A good result says `PASS` and reports completed evaluation laps. Zero completed laps or a worker failure says `NEEDS REVIEW`. In that case, paste the final `COPY THIS SANITY SUMMARY` block and any worker error; we should diagnose learning before the overnight run. Ten-minute success is an acceptance target, not a result already established by the developer bug checks.

## Step 3 — the 25-run benchmark

```powershell
.\.venv\Scripts\python.exe -m tools.benchmark_25
```

This runs all 25 PPO workers for about ten minutes each, then reports each worker's environment steps/s, aggregate throughput, system CPU use and estimated steps over twelve hours. It prints a recommendation. The target is at least 1,500 environment steps/s per worker; it is not yet verified on your laptop.

Watch CPU temperatures in your laptop manufacturer's monitoring utility. Use the limits recommended for your machine; the script cannot reliably read CPU temperature on every Windows laptop. Compare sustained performance after warming up, not just the first few seconds. A speed number alone does not establish a safe overnight setting.

If the recommendation suggests waves, compare:

```powershell
.\.venv\Scripts\python.exe -m tools.benchmark_25 --max-concurrent 12 --n-envs 4
```

All 25 still run, in up to three waves: allow roughly thirty minutes plus startup. Keep the configuration with healthy sustained temperatures and useful measured throughput. If speed remains low, paste the benchmark summary before the overnight run so the simulation can be profiled. Trying `--n-envs 8` is a separate comparison, not a guaranteed improvement.

## Step 4 — the overnight run

After handling, sanity and benchmark checks pass:

```powershell
.\.venv\Scripts\python.exe -m tools.train_all --hours 12 --max-concurrent 25 --n-envs 4
```

Replace 25 with your measured concurrency choice. Plug in AC, use Performance mode, keep vents clear, disable sleep while plugged in, and pause update restarts for the session. Check free disk space. Leave PowerShell open; the screen may turn off, but the computer must remain awake. You can close Codex and the chat.

Each run receives up to twelve active hours or 20 million lifetime environment steps, whichever comes first. With twelve workers, completing three waves can take up to 36 wall-clock hours. The time budget includes that worker's PPO updates and evaluation; it is not a promise that all runs finish within twelve wall-clock hours when using waves.

Reserve about **12 GiB** for default checkpoints/logs, plus the installed Python environment. The launcher uses a conservative 5 MiB per checkpoint estimate: 25 runs × approximately 82 bundles is about 10 GiB. Actual use depends on checkpoint size, repeated stops and step budgets. All checkpoints are retained for later tier selection. Increase the allowance if increasing `--steps` or saving more frequently.

This first real run writes `runs/physics_lock.json`. From then on, changing physics, cars, tracks, observations, actions or rewards requires retraining. Incompatible checkpoints are refused.

## Watching it

Open separate PowerShell windows in the project folder:

```powershell
.\.venv\Scripts\python.exe -m tools.monitor
.\.venv\Scripts\python.exe -m tools.training_wall
```

Run one command in each window. The monitor shows steps, speed, best evaluated lap, finish rate and status. It flags a run with no training lap after one million steps. A dash means no completed evaluation yet.

The Training Wall shows tracks as rows and cars as columns, playing saved policies at 0.4× speed. It refreshes checkpoints roughly every two minutes; waiting tiles are normal until the first save at 250,000 environment steps. It uses one CPU thread and a low frame rate. Its actual overhead with 25 models still needs measurement. Closing either viewer leaves training running. Add `--root` followed by the experiment path printed by a sanity/benchmark run to watch that experiment instead.

After evaluations have produced lap times, plot learning history:

```powershell
.\.venv\Scripts\python.exe -m tools.plot_history runs/sunrise_oval/atlas --output artifacts/atlas-learning.png
```

## If something goes wrong

- **A worker crashes:** the launcher restarts it from its latest complete checkpoint up to three times. Other workers continue. Inspect that run's `worker.log` if it remains failed.
- **Power cut or terminal closure:** rerun the same `train_all` command. It resumes weights, optimizer and normalization; unfinished work since the last checkpoint is lost. The original lifetime hour/step budget remains in force. Resumption is not a bit-for-bit replay of the interrupted episode.
- **Stop safely:** press Ctrl+C once in the launcher window and wait for workers to report stopped. They save final checkpoints. If a worker is unresponsive for 120 seconds, the launcher terminates it and reports that only its previous complete checkpoint is guaranteed.
- **Missing package, slow learning or version mismatch:** run `setup.cmd` for dependency errors; paste the sanity/benchmark summary for learning or throughput problems. A mismatch means the simulation changed: keep the old runs and use a new `--root` for deliberate retraining. Do not edit hashes to force a load.

## In the morning

```powershell
.\.venv\Scripts\python.exe -m tools.monitor --once
```

Expect all selected runs to be completed, with each driver finishing evaluated laps. Prefer a finish rate near 100%; finishing a budget without completing laps is not a successful driver. Review any `failed`, stale, or `NO FULL LAP` rows. A poor driver may need reward diagnosis or more training; extra hours alone are not guaranteed to fix it.

To add time to a compatible run that has already used its original budget, increase the **total** budget, for example:

```powershell
.\.venv\Scripts\python.exe -m tools.train_all --cars Rogue --tracks Grand_Circuit --hours 24 --steps 40000000 --max-concurrent 1
```

This resumes toward 24 lifetime active hours or 40 million lifetime steps. It does not start over. Building the four difficulty tiers comes in Phase 4.

## What to paste back

Paste the final sanity or benchmark summary, the command used, and the affected car/track. For a crash, include the last 30 lines of its `worker.log` and the error. Example:

```powershell
Get-Content runs\grand_circuit\rogue\worker.log -Tail 30
```

Do not paste entire logs or model files. Include whether the revised steering and edge recovery feel right before the physics is frozen.
