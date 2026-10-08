# Phase 3 report - 7 October 2026

Phase 3, the human game client, is implemented. `launch.cmd` opens the main menu. AI opponents, the checkpoint difficulty ladder and progression remain Phase 4. No training or checkpoint evaluation job was started.

## Delivered

- Main menu, five live car cards with comparison bars, five circuit previews with personal bests, pause menu, settings and results with lap splits.
- Three-lap Time Trial with a countdown, valid-lap timing, automatic best saves, state-recorded ghosts and progress-aligned delta. Invalid attempts restart at the start line without counting toward the three valid laps.
- Free Practice with a reset to the current centerline position, stopped and with an invalid lap. Practice cannot submit a Time Trial record.
- A 1920x1080 default resizable window, fullscreen toggle, 60 FPS presentation cap, interpolated motion, smooth camera/lookahead and speed-based zoom. High uses a 1440x810 logical canvas; Medium/Low reduce world resolution and effect limits while preserving UI readability.
- Cached track art, grid markings, cosmetic car silhouettes, visibly turning wheels, brake lights and soft shadows. Persistent session skid marks, smoke, dust, sparks, impact shake and speed streaks remain outside simulation state.
- Keyboard steering with the established ramp, primary-key rebinding, retained arrow keys, optional countersteering input assist, SDL controller analog steering/triggers and hotplug handling.
- In-memory sine/saw engine banks per car, tire screech, thumps, clicks and countdown tones. Master/engine/effects sliders, mute and silent fallback without an audio device.
- Atomic JSON player saves under `player_data/`, separate from `runs/`. Corrupt records are rejected; incompatible ghosts are ignored. The diagnostic viewer remains available separately.

## Preservation

The simulation hash remains:

```text
f9dee10155f30db652ce63fd8e3e6cca5f233fc6e199a13f8bb2037eda30b824
```

Byte comparisons confirm the original simulation source, cars, tracks, RL environment/reward and entire original `gt_academy/config.py` are unchanged. New presentation defaults are in `game/config.py`. The before/after inventory of all **8,608 files in runs/** is identical: names, sizes and modification timestamps. The game client has no training-write integration. Evidence: `artifacts/phase3/preservation.json`.

Read-only status inspection confirmed all 25 runs completed: 24 final evaluations at 100%, Grand Circuit / Comet at 2/3. This result is carried forward to Phase 4 without changing training data or frozen behavior.

## Verification

- **129 tests passed** in the final full suite, including the existing physics/RL tests.
- New tests cover save roundtrip, corrupted/wrong-version records, ghost heading wrap and progress delta, countdown isolation, Practice reset, and a real three-lap simulated session saving and reloading its best ghost.
- Menu/rebinding events, quality settings, pause-on-focus-loss, bounded effects, sound construction and render-state immutability passed.
- All **25 car/track client combinations** passed offscreen rendering. Screenshots of menus, selection screens, settings, driving, effects, pause and results are under `artifacts/phase3/` and were inspected.
- The real main loop passed an offscreen countdown-to-driving smoke test. Effect stress states are copies and cannot change production simulation behavior.
- After caching previews and reusing render buffers, High offscreen frame work measured **9.69 ms median / 12.54 ms p95** over 120 effect-stress frames at 1920x1080 output. Medium: 10.83 / 13.12 ms; Low: 10.55 / 12.66 ms. Reduced resolutions add an upscale pass, so are not guaranteed faster in this CPU-only check. These results exclude real display synchronization and do not certify live FPS.

## Play and acceptance

```powershell
Set-Location 'C:\Programming\Visual Studio Code\GT Academy'
.\launch.cmd
```

Choose a mode, car and circuit. The menu should appear within a few seconds; first-time track preparation may take a moment. WASD/arrows drive, Esc/P pauses, R restarts a trial or resets Practice, and F11 toggles fullscreen. Settings exposes quality, audio and controls. Records persist across restarts.

Hands-on acceptance remaining: live 60 FPS, controller feel and audible tone/volume balance on the user's hardware. A mapped DualSense was detected and neutral axes were read successfully, but interactive controller driving was not certified. No retraining is needed. Next phase: trained AI racing, checkpoint tiers and progression.

Historical reports: `docs/PHASE_1_REPORT.md`, `docs/PHASE_2_REPORT.md`, `docs/ARCADE_REVISION.md`.
