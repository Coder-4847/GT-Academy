# Phase 4 report - 7 October 2026

Phase 4 implements AI racing, difficulty exports, career progression and AI ghosts. Launch with `launch.cmd` and choose Race vs AI or Career.

## Delivered

- Four exported tiers for each of five cars on five circuits: 100 self-contained bundles with policy weights, frozen normalization, metadata and evaluation statistics.
- Read-only parallel checkpoint evaluation and resumable continuous-race screening. All 2,586 checkpoints have evaluation results: 670 saved results reused and 1,916 newly evaluated, with no evaluation errors.
- Every selected tier completed five continuous laps. Models that passed separate standing-start evaluations but failed rolling laps were replaced with reliable historical candidates. Grand Circuit / Comet has reliable exported opponents despite its final training checkpoint's 67% result.
- Race vs AI with independent rival car selection, 1–5 laps, countdown, on-track position, progress-aligned time gap, split results and optional AI noise/delay or time handicap.
- Career medals and unlocks: Rookie, Pro, Champion, next circuit; all five Champions unlock Legend. Three-lap career races disable custom handicaps. Progress and bests save atomically in player data.
- Live policy ghosts in Time Trial, with any tier available for practice. Cars do not collide with each other. AI uses the same physics and four-tick action cadence as training.

## Verification

- Full automated suite: **139 passed**. Covers frozen simulation and RL behavior, client sessions, input, save handling, tier selection, career gates, race results, action cadence, countdown isolation, time gaps and export integrity.
- All 100 final exports loaded successfully and produced identical actions to their source checkpoints for 12 sequential observations each.
- All 100 selections carry successful five-lap continuous-race evidence. `artifacts/phase4/race-validation.json` records final results and export parity; `continuous-race-checks.json` also records rejected candidates. `pre-vetting-race-validation.json` preserves the earlier diagnostic failures.
- Actual exported policies exercised the game renderer and menus offscreen. Screenshots and frame timing measurements are under `artifacts/phase4/`. These are integration checks, not live display FPS certification.

## Preservation

Simulation hash remains `f9dee10155f30db652ce63fd8e3e6cca5f233fc6e199a13f8bb2037eda30b824`.

Original simulation sources, car stats, tracks, observations, rewards and the entire original configuration file remain byte-identical. The inventory of all **8,608 files under runs/** retains identical paths, sizes and modification timestamps. Evidence: `artifacts/phase4/preservation.json`. No retraining occurred.

## Limits and acceptance

The checkpoint history does not provide every intended difficulty gap. The final manifest contains **36 pace-spacing warnings**; some adjacent tiers are nearly identical, and some Rookie opponents exceed the intended difficulty. Custom-race handicaps are available, while career preserves the selected policies. Five-lap checks cover the default deterministic start without optional mistakes; they do not guarantee failure-free driving under all settings.

Human difficulty balance, controller feel and live display smoothness still need a play-through. Phase 5 remains the next master-plan phase. Earlier client work is recorded in `docs/PHASE_3_REPORT.md`.
