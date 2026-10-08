# Final phase report - 7 October 2026

Phase 5 code is implemented: replay, clean photos, performance and audio polish, robustness checks, and a Windows source distribution. The frozen game simulation and training data are preserved. Sustained live-play performance and installation on a genuinely fresh Windows machine remain user acceptance checks.

## What was built

- Automatic replay of the final twelve seconds after an AI race, interpolated from bounded 30 Hz pose snapshots. Space pauses, Esc skips, and results offer Watch replay. Playback is silent and never advances simulation, changes lap results or awards medals again.
- F12 saves a clean 1440×810 PNG under `player_data/screenshots/`, including from paused replay. Screenshot filenames are unique.
- High-quality rendering reuses bounded crop surfaces and avoids redundant full-frame clears. Profiling identified scaling and surface operations as the largest costs. No quality reduction or simulation timing change was made.
- Repeated wall impacts are rate-limited in the audio layer to avoid a harsh buzz. The muted palette, smooth follow camera and generated art remain consistent with the brief.
- Damaged manifest/archive errors are presented clearly. Regression checks exercise corrupt save shapes, model hash checks, focus loss, unplug events, resize and replay isolation.
- `setup.cmd` installs the exact tested Python 3.12 dependencies and runs tests; `launch.cmd` starts the game; `package.cmd` builds a checksum-verified ZIP with all 100 chosen AI bundles. The ZIP excludes training and personal data. This is a source distribution, not a single executable.

## Commands

On this machine, run `.\launch.cmd`. To rebuild the shareable ZIP, run `.\package.cmd`.

On a fresh Windows machine, install 64-bit Python 3.12 with its launcher, extract `artifacts/GT-Academy-Windows.zip`, open PowerShell in the extracted `GT Academy` directory, then run:

```powershell
.\setup.cmd
.\launch.cmd
```

First setup requires internet and may take several minutes. No training is needed. Source-only clones need the exported `assets/ai/` folder copied from the distribution for AI modes.

## Verification and performance

The full suite passes **149 tests**, including existing lap and simulation checks. A real exported policy drove both independent cars through a complete 31.295-second lap: both finished with exactly equal times, the twelve-second replay played automatically, and playback left the final simulation state identical. A clean PNG was saved and replay/results screenshots were inspected.

Frame workload: High, 1920×1080 output, real CPU policy, particles, 60 Hz simulation, 60 warm-up frames per track. Offscreen before/after runs measured 360 frames per track. The real Windows display check measured 180 frames per track. Values below are **median / 95th-percentile milliseconds**; a 60 FPS budget is 16.67 ms.

| Circuit | Before, offscreen | After, offscreen | After, Windows display |
| --- | ---: | ---: | ---: |
| Sunrise Oval | 9.37 / 10.60 | 8.15 / 9.68 | 8.77 / 10.27 |
| Hairpin Valley | 9.45 / 10.97 | 8.42 / 10.14 | 8.79 / 10.17 |
| Esses Run | 9.15 / 10.41 | 8.54 / 10.27 | 9.40 / 11.50 |
| Longshot Speedway | 9.88 / 11.49 | 8.30 / 9.79 | 10.50 / 12.76 |
| Grand Circuit | 9.46 / 10.50 | 8.22 / 9.49 | 9.85 / 12.42 |

All 1,800 final offscreen measured frames met the budget. The short real-display workload had one frame above budget out of 900. These are uncapped workload measurements with audio disabled, not a sustained 60 FPS certification. The last real-display tracks overlapped a separate integration check, so their extra load is disclosed rather than treating the difference as a rendering regression. Repeat `python -m tools.profile_game --window --frames 600 --label my-display` for a longer local check, then play a race with audio enabled.

Evidence is in `artifacts/phase5/`: before/after/window JSON, `profile.pstats`, `integration.json`, screenshots and `preservation.json`.

## Architecture at a glance

| Layer | Responsibility and data flow |
| --- | --- |
| Frozen simulation | `sim/`, original `config.py`, cars and tracks define deterministic 60 Hz dynamics, collision hulls, gates and observations. No Pygame or wall clock enters physics. |
| Learning | `rl/env.py` exposes the frozen observation/action contract. PPO training and immutable checkpoint storage live separately. Rewards favor new forward progress and valid clean laps, penalizing damage, off-road time and wasted motion. |
| Export and inference | Evaluation reads checkpoints; tier selection screens standing-start and five-lap reliability. Bundles pair weights with normalization and identity/hash metadata. CPU inference acts every four physics ticks. |
| Game sessions | Human inputs and AI actions enter independent instances of the same simulation. Time Trial, Practice, races, progress-aligned gaps and Career medals live in `game/session.py` and `racing.py`. Cars do not collide with each other. |
| Presentation | The client schedules fixed ticks and interpolated rendering. Cached scenery, bounded effects, camera and synthesized audio read states. Replays store bounded copies of poses and never drive simulation. |
| Persistence | Atomic player JSON holds settings, records, ghosts and unlocks. Photos and inference cache are separate. The client has no training-write path. |
| Distribution | Windows setup/launch scripts, an exact environment lock and a validated source/model ZIP. All graphics and sounds are procedural. |

## Freeze and limits

Simulation hash: `f9dee10155f30db652ce63fd8e3e6cca5f233fc6e199a13f8bb2037eda30b824`.

Byte checks confirm frozen sources are unchanged. All **8,608 files in runs/** retain identical paths, sizes and modification timestamps. No training ran.

The Phase 4 tier-spacing limitation remains: 36 warnings identify missing target pace bands or nearly identical adjacent tiers. No policies or frozen behavior were adjusted to hide it. Replay retains only the current session's final twelve seconds; it is not a video exporter. Camera feel, audio comfort, long-session frame pacing and fresh-machine dependency installation still require hands-on acceptance.

Earlier phase reports are in `docs/`. `README.md` is the play/setup guide; `TRAINING_GUIDE.md` documents optional future training and its pre-flight checks.
