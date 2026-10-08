# GT Academy

**Browser edition:** [Play on GitHub Pages](https://coder-4847.github.io/GT-Academy/). Choose a mode, car and circuit from the main menu. See [browser release notes](docs/BROWSER_RELEASE.md) for controls, validation and browser-specific limitations. The Python desktop edition remains available below.

A procedural 2D racing game with five cars and five circuits. **Phase 5 is implemented:** post-race replays, clean screenshots, performance polish and Windows packaging, plus Race vs AI, four opponent tiers for all 25 car/track pairs, career progression and AI ghosts, alongside Time Trial, Free Practice, effects, audio and settings.

All 25 training runs are complete. Final evaluations show 24 pairs at 100% completion and Grand Circuit / Comet at 67%. The production `runs/` folder is preserved; the client does not write to it. The exported library selects reliable historical checkpoints, including a Grand Circuit / Comet model that completes five continuous laps.

## Play

```powershell
Set-Location 'C:\Programming\Visual Studio Code\GT Academy'
.\launch.cmd
```

Or double-click `launch.cmd`. The main menu opens in a 1920x1080 resizable window with a 60 FPS cap. Choose a mode, car and circuit, then **Start driving**. First-time track art preparation may take a moment.

- **Time Trial:** a three-second countdown, then three valid laps. Beat your personal best to save its ghost. The blue outline replays it; a negative delta means you are ahead. Invalid laps do not count. Cross the start line for a fresh attempt or press R to restart.
- **Free Practice:** explore without a deadline. R places the car on the centerline at rest and invalidates the current lap. Pause -> Finish session ends practice. Personal-best ghosts are earned in Time Trial.
- **Race vs AI:** choose your rival car independently, any tier and 1–5 laps. Optional AI mistakes and a time penalty make custom races easier; they do not earn career medals. Cars pass through each other.
- **Career:** every car, circuit and difficulty (including Legend) is always available. Wins record medals without requiring earlier wins. Career uses three laps without custom handicaps.
- **AI ghost:** in Time Trial, choose a tier to race its live policy ghost instead of your personal ghost. All tiers are available for this practice mode.
- **Replay:** completed AI races automatically replay the final 12 seconds with a smooth follow camera. Space pauses; Esc skips to results. Use Watch replay on the results screen to play it again. Replays last only for the current session.
- **Photos:** F12 saves a clean 1440×810 PNG under `player_data/screenshots/` during driving, pause, results or replay.
- **Settings:** High/Medium/Low quality, fullscreen, optional countersteering input assistance, master/engine/effects volume, mute and key rebinding.

| Control | Action |
| --- | --- |
| W / Up | Throttle |
| S / Down | Brake |
| A / D or Left / Right | Steering |
| R | Restart Time Trial / reset Practice to track |
| Esc / P | Pause; Esc resumes from Pause |
| F11 | Fullscreen / windowed |
| F12 | Save a clean driving/replay image |
| Space / Esc during replay | Pause replay / go to results |
| Mouse | Menu buttons and volume sliders |
| Up / Down / Tab, Enter | Menu navigation and selection |
| Xbox-style left stick | Analog steering |
| RT / LT | Throttle / brake |
| Controller Start | Pause / resume |
| Controller D-pad, A / B | Navigate, select / back |

SDL-mapped controllers, including compatible PlayStation devices, are supported. Losing focus or unplugging a controller pauses driving. Arrow keys always remain available after rebinding. The game continues silently if no audio device is available.

Settings, career medals, race bests, times and ghosts live in **`player_data/profile.json`**, separate from training. Writes replace the JSON atomically; incompatible ghosts are ignored. Keep that file to retain your records. Save errors appear in the game without ending the session.

## Setup

On a fresh Windows machine, install **64-bit Python 3.12** with its launcher, extract the Windows distribution, and open PowerShell in its `GT Academy` folder:

```powershell
.\setup.cmd
.\launch.cmd
```

Setup installs the exact tested versions from `requirements-lock.txt`, then runs the tests. Expect `149 passed` and `Ready. Run launch.cmd to drive.` The first setup needs internet and several minutes for CPU PyTorch and other dependencies; it does not train any models. No activation is needed. All graphics and audio are generated in code.

The Windows distribution includes all 100 AI bundles. The GitHub repository includes the exported `assets/ai/` folder for desktop AI modes. If using a source copy without that folder, restore it from the distribution or rebuild from existing training checkpoints. Human Time Trial and Free Practice work without AI files.

To create a shareable distribution on this machine:

```powershell
.\package.cmd
```

Share `artifacts/GT-Academy-Windows.zip`. It contains source, guides, tests, setup/launch scripts and all chosen AI models, with file checksums. It excludes `runs/`, personal saves, screenshots, development artifacts and the virtual environment. This is a Python source distribution; Python 3.12 and internet for initial dependency installation are required. The optional single-executable route was not used.

## Driving laboratory

The original diagnostic viewer is still available:

```powershell
.\.venv\Scripts\python.exe -m tools.debug_drive
```

Laboratory controls: 1-5 selects cars, T switches track, M toggles the map, Tab opens telemetry, V shows rays, F shows forces and H shows relative data. These are separate from the main game's menus.

## Training

Production training is complete. **Phase 5 requires no retraining.** Preserve all checkpoint history. Exported opponents live separately in `assets/ai/`; the game extracts validated inference files to `player_data/ai_cache/`. [TRAINING_GUIDE.md](TRAINING_GUIDE.md) remains the reference for any future training you explicitly choose to run. Do not change frozen behavior to improve the remaining Comet result.

For any future training you explicitly choose to run, follow the complete [training guide](TRAINING_GUIDE.md). Pre-flight: preserve the frozen simulation and back up checkpoints; plug in the laptop, select performance mode and check ventilation; run the ten-minute sanity test and the 25-worker benchmark; check temperatures and choose the supported worker count before starting an overnight job. Those commands actually train models; they are unnecessary to play this release.

Read-only monitoring:

```powershell
.\.venv\Scripts\python.exe -m tools.monitor
.\.venv\Scripts\python.exe -m tools.training_wall
.\.venv\Scripts\python.exe -m tools.plot_history runs/sunrise_oval/atlas --output artifacts/atlas-learning.png
```

The launcher resumes selected pairs from compatible checkpoints. Step/hour budgets are lifetime totals. Checkpoints normally save every 250,000 steps and on graceful termination, including policy, optimizer, normalization, identity, checksums and simulation hash. `best.json` points to the most reliable, then fastest evaluated checkpoint.

## Opponent library

The current library is ready to play: 100 exported tiers, each selected from checkpoints that passed five continuous laps. Evaluation covers all 2,586 checkpoints (670 saved evaluations reused, 1,916 newly evaluated). No training ran.

To reproduce selection and export without modifying training files:

```powershell
.\.venv\Scripts\python.exe -m tools.evaluate_checkpoints --workers 4
.\.venv\Scripts\python.exe -m tools.prepare_opponents --workers 4
```

These CPU jobs save resumable reports under `artifacts/`. To re-export the existing vetted selection quickly:

```powershell
.\.venv\Scripts\python.exe -m tools.build_tiers --results artifacts/phase4/race-vetted-evaluations.json
```

Difficulty targets are approximate. Some reliable checkpoints have nearly identical pace, and some Rookie tiers are faster than the intended 130–145% of Legend lap time. The manifest lists 36 spacing warnings. Custom race handicaps can help; career retains the unmodified policies. Five-lap validation is evidence for the tested deterministic start, not a guarantee under optional AI mistakes.

## Architecture and freeze

| Area | Responsibility |
| --- | --- |
| `sim/`, `cars.py`, `tracks.py` | Frozen deterministic 60 Hz physics, actuators, geometry, surfaces, collisions and lap gates |
| `rl/env.py`, `rl/reward.py` | Frozen observation/action contract, episode rules and progress reward |
| `rl/training.py`, `storage.py`, `launcher.py` | PPO, checkpoint integrity, workers and recovery |
| `rl/tiers.py`, `tools/prepare_opponents.py` | Read-only evaluation selection and validated bundle export |
| `game/replay.py` | Bounded copies of recent poses; playback never advances simulation or awards medals |
| `game/racing.py` | Frozen-policy opponents, races, live AI ghosts and career gates |
| `game/client.py` | Menus, settings, scheduling and HUD |
| `game/session.py`, `save.py` | Sessions, ghosts, delta timing and player saves |
| `game/renderer.py`, `audio.py`, `controls.py` | Cached art, effects, synthesized sounds and human actions |
| `game/config.py` | Presentation defaults, separate from frozen configuration |

Frozen hash: `f9dee10155f30db652ce63fd8e3e6cca5f233fc6e199a13f8bb2037eda30b824`.

Humans and AI use the same physics. Arcade road steering holds grip; gravel progressively releases stabilization into tire dynamics. Gates reject reverse laps and shortcuts. Training rewards new forward progress, with penalties for impacts, leaving the road, wasted time and abrupt actions. See [docs/OBSERVATIONS.md](docs/OBSERVATIONS.md) for the 32-float observation layout.

## Verification and troubleshooting

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m tools.verify_client
```

The second command performs short offscreen bug checks and writes screenshots/timings under `artifacts/phase3/`. It is not a training job or live-FPS certification.

To repeat the Phase 5 race workload on the real display:

```powershell
.\.venv\Scripts\python.exe -m tools.profile_game --window --frames 600 --label my-display
```

This opens a window and runs an uncapped High-quality workload with real AI and particles across five tracks. Results are saved to `artifacts/phase5/my-display.json`. Audio is disabled for repeatability. A 60 FPS frame budget is 16.7 ms; this check does not replace a sustained manual race with audio and your normal applications running.

- **No movement:** finish the countdown or resume from Pause. Brake does not engage reverse.
- **No ghost:** complete a valid Time Trial lap. Records are separate for every car/track pair.
- **Low frame rate:** try a smaller window and another quality setting. Quality never changes physics.
- **No sound:** check mute/volume and audio-device status in Settings. Restart after changing the system audio device.
- **Disconnected controller:** use the keyboard or reconnect, then resume.
- **Save warning:** check that the project folder is writable. Player saves do not use training checkpoints.
- **Missing dependencies:** run `setup.cmd` and use the project `.venv` interpreter.
- **Missing AI:** install `assets/ai/` from the distribution, or run the documented evaluation/export commands using your existing checkpoints.
- **Corrupt AI cache:** close the game and remove only `player_data/ai_cache/`; it is regenerated from validated exports. If a bundle checksum fails, restore `assets/ai/` from a known-good distribution.
- **Model version mismatch:** never edit stamps to bypass validation; preserve the original training files.

[PHASE_REPORT.md](PHASE_REPORT.md) records validation and hands-on acceptance. [DECISIONS.md](DECISIONS.md) explains choices. Historical reports are under `docs/`.
