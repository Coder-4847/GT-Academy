# Design decisions

## Always-open challenges — 8 October 2026

The user requested that every car, track and difficulty be available at all times. Both browser and desktop now remove progression requirements, including Career and Legend. Medals remain a record of wins, and no prior medals are required to enter or earn another challenge. This supersedes historical unlock rules below; simulation, trained models and training files are unchanged.

## Phase 5 update - 7 October 2026

- The final twelve seconds are recorded at 30 Hz in a bounded in-memory ring of copied player/rival poses. Playback interpolates these snapshots with a follow camera; it never steps simulation, recomputes outcomes or writes medals. Playback is silent and omits transient particles from the end of the race; existing session skid marks remain cosmetic scenery.
- F12 captures the logical 1440×810 scene without menus/HUD, including paused playback. Photos use unique timestamp filenames in player data. They do not modify physics or replays.
- Profiling found smooth scaling and surface operations dominant. Reusing at most four crop surfaces and avoiding redundant full-screen clears reduced measured frame cost without lowering High quality or changing physics cadence.
- Sustained wall contact is limited to one synthesized impact event per 150 ms to avoid a harsh repeated buzz. Existing restrained camera motion, palette and procedural art are retained.
- Malformed manifest structures, corrupt archives, bad normalization serialization and invalid statistics report errors through the client. Missing/corrupt saves, focus loss, controller removal, window resize and replay isolation have regression tests.
- Windows setup uses the exact tested Python 3.12 dependency lock. The shareable source ZIP includes all validated AI bundles and checksums, but excludes training, personal data and virtual environments. A single executable is optional in the plan and is not shipped.
- Automated performance measurements are short workload checks. Fresh-machine installation and sustained 60 FPS with live audio remain acceptance checks, not claims inferred from passing tests.

## Phase 4 update - 7 October 2026

- All 2,586 checkpoints have three-episode evaluation results: 670 existing results reused and 1,916 computed read-only. Reports and process-pool caches are outside `runs/`.
- Standing-start evaluation alone did not predict rolling-lap reliability. Selection now rejects candidates that fail five continuous race laps, then searches the remaining historical checkpoints. All 100 final tier bundles pass this check.
- Tier pace uses mean evaluation lap time. Rookie targets 130–145% of the fastest reliable policy, Pro 112%, Champion 103% and Legend the fastest. Historical policies do not fill every band; 36 manifest warnings disclose weak spacing. No policy or physics was altered to manufacture a gap.
- Bundles contain weights, frozen normalization, original metadata and evaluation statistics. Source checksums, simulation identity, car/track identity and bundle checksums are validated before use.
- CPU inference runs every four physics ticks, matching training. Each driver has a separate instance of the same frozen simulation. Cars start at the trained grid position and overlap without inter-car collision; rendering interpolates both independently.
- Custom races allow independent rival cars, 1–5 laps, optional action noise/delay and a result time penalty. Career fixes three laps without these aids. Choosing a slower rival car remains possible.
- Career unlocks are saved by circuit/tier: Rookie to Pro to Champion, Champion to the next circuit, and all Champions to Legend. Abandoned sessions and custom races cannot award career medals.
- AI ghosts run one lap per human attempt using the same policies. Existing personal Time Trial records remain independent of career and race bests.
- The full suite passes 139 tests. Live display performance and human difficulty balance still require a play-through; offscreen checks do not certify those experiences.

## Phase 3 update - 7 October 2026

- Production training is complete. The user's freeze instruction supersedes the historical pre-training notes below. Original simulation configuration and hashed source files remain byte-identical; all 8,608 training files retain names, sizes and modification timestamps.
- The next phase is the human client. It does not load models yet; checkpoint tiers and the 67% Grand Circuit / Comet result belong to Phase 4.
- Client defaults are isolated in `game/config.py`. Cosmetic silhouettes never change collision shapes. Optional steering assistance transforms human input only, through the same actuator limits.
- Time Trial ends after three valid laps. Best ghosts are keyed by car/track and recorded at 30 Hz, with interpolated exact start-line crossings. Save-level simulation stamping prevents incompatible replays. Delta uses monotonic progress. A standing-start attempt can race a rolling-start ghost from an earlier session.
- Practice has no deadline and never submits a Time Trial record. Its reset places the human back on the current centerline at rest with an invalid lap; core lap rules remain untouched.
- Player data lives in `player_data/profile.json`. Writes use a temporary file then atomic replacement; malformed data falls back with a message. No external art, audio or heavy dependencies were added.
- Cached track art and skid layers are separate. Quality scales world resolution and bounded particle counts. The 1440x810 logical canvas scales to the default 1920x1080 output. Simulation stays fixed at 60 Hz; interpolation never writes to sim state.
- `launch.cmd` now opens the main game. The laboratory remains `python -m tools.debug_drive`. Controller/audio feel and live display performance still need the user's play-through.

## Historical Phases 1-2 decisions

The supplied GT Academy master plan is the design authority. Phases 1 and 2 are implemented. The user's driving feedback authorized steering, road-edge and track revisions before continuing to Phase 2. Only isolated developer training bug checks have run; learning acceptance, the laptop benchmark and real training remain user-run.

- The workspace is the project root; the Python package is `gt_academy/`. An extra enclosing directory was unnecessary in the already named GT Academy workspace.
- Python 3.12 is the verification interpreter. This machine's registered Python is 3.13, so the existing `.venv` was created using the Codex bundled Python 3.12.14. Fresh installs use the standard Python 3.12 or 3.11 launcher through `setup.cmd`. Phase 2 adds CPU-only PyTorch 2.8.0, Stable-Baselines3, Gymnasium and the requested matplotlib history plotter to NumPy, pygame-ce and pytest.
- All five original masses, powers, top speeds, axle friction coefficients, braking ratings and steering locks are retained. Launch acceleration caps are Atlas 6.4, Bolt 8.0, Vector 6.0, Comet 6.8 and Rogue 7.4 m/s² before traction limits. These make Bolt quickest to 100 km/h. Wheelbase is 2.65 m, static front weight is 48%, and centre-of-gravity height is 0.48 m for each car.
- Aerodynamic drag is derived from power and target top speed, including rolling resistance. It is an effective game calibration coefficient, not a claimed measured drag area of a real car. SI units are used internally.
- The tire model uses a smooth Magic Formula shape with a gradual post-peak falloff. Longitudinal force has priority inside an axle's friction circle; turning force uses the remaining budget. Rear-wheel drive and longitudinal weight transfer make throttle-induced oversteer possible. Lateral load transfer, individual wheel rotation and a gearbox are outside Phase 1.
- Each 1/60 s simulation tick has three fixed integration substeps. At 270 km/h the car travels approximately 0.42 m per substep. A three-circle hull is projected inside the walls each substep; impacts lose normal velocity and tangential speed and can impart yaw. Cars do not collide with each other.
- Low-speed dynamics blend from kinematic to dynamic between 1 and 5 m/s, centred around the requested 3 m/s. The brake pedal stops the car and does not act as a reverse gear. Collision-induced backwards motion remains possible.
- Closed uniform cubic B-splines round the hand-placed track control points. Geometry is scaled to the specified length and resampled at approximately 1 m. The last segment closes back to sample zero; the first sample is not duplicated. Run-off is 6 m on each side. Grass is the Phase 1 off-road surface; a separate gravel class is unnecessary because the brief gives both the same handling role.
- Import-time validation checks target length, sample spacing including the closing segment, curvature that would fold offset walls, and nonadjacent corridor separation. The shapes are non-overlapping. These are compact original layouts, not replicas of existing circuits.
- Nearest-segment queries use a fixed 33-segment neighborhood with a retained index. Full-track search is reserved for spawn or explicit relocation. Batch queries amortise wheel and hull work. A stable tie-break at vertices makes local and global queries agree. Teleporting a car requires refreshing its index, offset and progress before stepping.
- Ordered lap gates sit at 12 equal intervals. A completed lap requires all gates, a forward start crossing and a full course's net progress. Leaving asphalt plus the kerb allowance invalidates that lap. Returning to the start begins a fresh attempt. A gate must be crossed within the asphalt width. These rules intentionally favour reliable anti-shortcut validation over forgiving lap timing.
- The observation contract has 32 float32 entries and two actions. All observations are clipped to [-1, 1]. Distances and actuator states occupy [0, 1]; wheel asphalt flags are -1 or +1. Ray range is 70 m with 11 rays from -100° to +100°. Grass starts with zero asphalt ray clearance. See `docs/OBSERVATIONS.md` for the exact layout.
- The simulation hash uses the parsed source of physics, geometry, cars, state, laps, collisions, observation code, the RL environment and reward, plus their five simulation configuration classes. Viewer settings, game rendering and optimizer hyperparameters are excluded. Source formatting and ordinary comments do not affect it. Car and track colours currently reside in their definitions; changing those source definitions also changes the stamp, so later visual-only variants should live in the renderer.
- Numba is deferred until the user-run benchmark establishes a need. The short agent-side benchmark is a bug check only, not a claim about laptop training throughput. The Phase 2 target of 1,500 environment steps/s per process is not certified by this delivery.
- The debug viewer adds a restrained cached track view and live force/ray overlays but remains a physics tool. Final menus, sound, ghosts, smoke, trained opponents and progression belong to the later phases.
- Human handling quality and the 6–12% best-lap balance goal need driving feedback and strong trained policies. Automated tests do not establish that balance or certify 60 FPS on the laptop.

## Changes after driving feedback

- Keyboard steering ramp increased from 3 to 7 units/s; physical steering rate from 1.9 to 3.2 rad/s; steering response from 12 to 22 s⁻¹; speed-lock scale from 26 to 30 m/s. The car retains speed-sensitive steering and actuator weight. A regression check requires meaningful response within 150 ms at 72 km/h.
- Run-off grip increased from 0.55 to 0.72 and drag reduced from 0.65 to 0.18 s⁻¹. A 1.6 m smooth transition beyond asphalt/kerbs replaces the abrupt handling step. A small drive-force reserve preserves some lateral authority at the rear. These apply equally to humans and policies. A light-edge-graze check retains more than 94% axle grip.
- Sunrise gained a modest braking kink; Esses gained more pronounced direction changes; Longshot gained two chicanes. Hairpin Valley and Grand Circuit already provide tighter/technical challenges. The five names, lengths and model-pair count stay consistent. Original layouts meet the request without taking up the optional suggestion to copy F1 circuits.

## Phase 2 choices

- Four 60 Hz physics steps per policy action, four in-process environments per worker by default, and one CPU/BLAS thread per worker. Both driver types use the same physical actuator limits.
- Randomized starts cover the course, with 35% anchored to the start area. Heading, lateral offset and speed are perturbed. A partial first circuit never counts as a full lap. Evaluation uses three reproducible standing-grid variants.
- Progress reward has an unwrapped high-water mark. Reversing cannot earn the same distance twice; off-course progress is consumed without reward, so re-entry cannot cash it in. Ordered gates and invalid-jump checks remain authoritative. Time, grass, impacts and abrupt actions cost reward; full valid laps earn a speed-scaled bonus.
- PPO uses two 256-unit tanh layers, gamma 0.995, GAE 0.95, 1024 rollout steps per environment, 256-sample batches, 10 epochs, entropy 0.005 and a learning rate declining from 0.0003 toward 0.00005. Defaults live in `config.py`; overrides are recorded in checkpoints.
- A checkpoint is an immutable directory named with its actual environment-step count. It contains weights/optimizer, VecNormalize statistics, metadata and file checksums. A completed directory is atomically published before `latest.json` changes. Partial saves are ignored; a corrupted latest bundle falls back to an older complete bundle. A simulation mismatch never silently falls back.
- `best.json` points separately to the most reliable, then fastest, evaluated checkpoint. Retaining checkpoints preserves those exact weights and normalization without duplicating them. Evaluation JSON and lap-history CSV are stored separately from frozen weights.
- Resuming restores optimizer, policy and normalization. Hour and step limits are lifetime per-run targets; increasing them adds training. Episodes restart and RNG state is not a bit-for-bit continuation. A crash can lose unsaved steps.
- Real training creates a physics lock in its output root. Sanity and benchmark runs use separate experiment roots without freezing production physics. Every checkpoint still carries a hash. Do not change physics under running workers.
- Windows venv Python has a redirector whose PID can differ from the worker's. A unique worker token identifies startup/status across that boundary. Ctrl+C requests a shared stop file; after a 120-second grace period, only the owned worker process tree is forcibly terminated. A per-run OS file lock prevents concurrent writers and releases on crashes.
- Below-normal priority and a concurrency cap are defaults. Failed workers restart up to three times. A genuinely unresponsive worker cannot be guaranteed a final checkpoint; the launcher reports that limitation.
- The Training Wall loads one tile per frame, refreshes roughly every two minutes and plays at 6 FPS / 0.4× simulated speed. It uses one CPU thread and has no training-control channel. Its full 25-model overhead is unmeasured on the laptop.
- All checkpoint history is retained for Phase 4 tiers. The conservative default allowance is about 10 GiB for 25 runs at 20 million steps and 250,000-step intervals; reserve 12 GiB plus dependencies. Additional stops or longer budgets increase it.

The developer checks have **not frozen production physics**. Re-drive the changes, run the user-side sanity/benchmark steps, and resolve issues before real training. The launcher records the freeze when that run begins.
