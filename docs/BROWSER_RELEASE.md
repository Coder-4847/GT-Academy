# Browser release — 8 October 2026

The GitHub Pages edition is a static browser client for the existing GT Academy simulation. The desktop game remains available through `launch.cmd`.

## Play

The intended Pages address is **https://coder-4847.github.io/GT-Academy/**. Choose Drive, select a mode, car and circuit, then Start driving. Garage compares cars; Circuits shows layouts and records; Settings controls rendering, sound and steering assistance. The first visit downloads the bundled Python runtime; subsequent visits benefit from the browser cache.

Keyboard: WASD or arrow keys to drive, Esc/P to pause, R for Practice reset, F for a clean image. Gamepads use the left stick, triggers and Start. Narrow screens provide touch buttons. Focus loss pauses driving. Finished races include a short replay.

Settings and progress live in browser local storage. They are separate from desktop saves. Settings offers backup/restore of browser progress. Private browsing or clearing site data can remove these records.

## What is preserved

- The original Python simulation, cars, tracks, observations and rewards are archived byte-for-byte in `web/simulation.zip`. The browser verifies the archive checksum and the original simulation hash before allowing play.
- Pyodide 0.27.7 runs Python 3.12 and NumPy in a dedicated Web Worker. Rendering and menu animation use browser canvas/DOM on the main thread. The runtime is vendored under `web/vendor/pyodide/`; no runtime CDN is needed.
- Original session logic implements lap validation, races, ghosts, career medals and results. Inputs retain the existing keyboard ramp and actuator behavior.
- Trained actor weights and frozen observation normalization are exported into safe numeric NPZ files. No PyTorch, training or pickle loading is needed by the browser. Model checksums, car/track identities and simulation versions are checked before use.
- Export comparison covered 2,400 observations across 100 source actors; maximum action difference was below 0.000001. Small arithmetic differences can still change a long driving trajectory, so browser lap testing is separate from desktop testing.

## Browser opponent selection

All 100 original candidate exports were tested for five continuous laps in the actual WebAssembly runtime. 87 passed; 13 failed. The published tier catalog uses only passing candidates, giving all 100 car/track/tier slots a validated driver. It uses 76 distinct models. Some tiers share a model where the reliable candidates do not provide the desired pace gap; the catalog includes 58 spacing warnings. Custom races offer a rival time penalty. This selection changes neither weights nor desktop bundles, and performs no retraining.

## Verification

Automated Edge checks cover runtime startup, car and track selection, driving, AI racing, pause controls, settings persistence and a 390-pixel mobile layout. Screenshots were visually inspected. Adapter regression checks verify identical Practice trajectories and prevent a retained Time Trial ghost setting from creating an AI race in Practice. The existing desktop suite remains applicable to the unchanged simulation.

Short automated checks do not establish sustained frame rates on every phone or browser. High quality uses up to 2× device-pixel rendering; Medium uses 1×. Try Medium on slower devices. The first engine load and first policy load have explicit loading states.

## Development and deployment

Serve the site locally:

```powershell
.\.venv\Scripts\python.exe -m http.server 8766 --directory web
```

Open `http://localhost:8766/`. Opening the HTML directly as a file will not work because the worker and runtime require HTTP.

`tools/build_web.py` exports original actors and frozen source; `tools/fetch_web_runtime.py` downloads the pinned runtime. After rebuilding actors, run `tools/verify_web_models.cjs` in Edge and then `tools/select_web_tiers.py` to select browser-validated tiers. Do not deploy an unvalidated rebuilt catalog. The browser test scripts use Playwright supplied through `PLAYWRIGHT_MODULE` or an installed `playwright` package.

Pushes to `main` trigger `.github/workflows/pages.yml`, which checks the browser modules and deploys only `web/` to GitHub Pages. Repository source and exported desktop bundles are separate from the Pages artifact. Training files, personal saves, virtual environments and development artifacts are excluded from Git.

Runtime references: [Pyodide 0.27.7](https://pyodide.org/en/0.27.7/usage/quickstart.html) and [GitHub Pages Actions deployment](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).

## Loading recovery update

Start driving remains available during background downloads in every mode. Clicking it shows the current download stage and received megabytes, with a Back to menu option. The pinned runtime is cached in browser Cache Storage. Network requests have a 45-second timeout; startup has a 90-second limit and a Retry loading action. A failed load no longer leaves a permanently disabled button. Slow-load, cancellation, blocked-request recovery and cache reuse are covered by `tools/verify_loading.cjs`. No checkpoint, physics or training-file changes were made.

## Open challenges

Every car, track and tier is available immediately in both browser and desktop editions, including Career and Legend. Career wins still save medals; no earlier wins are required, and choosing another circuit preserves your selected tier. This supersedes the original progression restrictions.
