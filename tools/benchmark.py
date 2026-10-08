"""Short, user-run throughput benchmark. Does not train any policies."""
import argparse
from math import sin
from time import perf_counter
import sys
from pathlib import Path

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gt_academy.cars import CARS
from gt_academy.tracks import TRACKS
from gt_academy.sim import Simulation, observation, SIM_VERSION


def benchmark(steps: int, sensors: bool) -> float:
    sim = Simulation(CARS[0],TRACKS[0])
    start = perf_counter()
    for i in range(steps):
        if i % 1200 == 0:
            sim.reset()
        sim.step((0.15*sin(i/120),0.8))
        if sensors:
            observation(sim.state,sim.car,sim.track)
    return steps/(perf_counter()-start)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--steps',type=int,default=10000)
    parser.add_argument('--bug-check',action='store_true',help='Label agent-side verification; not a hardware recommendation')
    args = parser.parse_args()
    if args.steps <= 0:
        parser.error('--steps must be positive')
    print('BUG CHECK ONLY; not a laptop training benchmark' if args.bug_check else 'Single-process headless benchmark')
    print(f'Python {sys.version.split()[0]} | sim {SIM_VERSION}')
    print('Backend: Python + NumPy; Numba is not used.')
    benchmark(min(args.steps,120),False)
    for sensors in (False,True):
        rate = benchmark(args.steps,sensors)
        print(f'{"Physics + observation" if sensors else "Physics only":24} {rate:,.0f} sim steps/s ({1000/rate:.3f} ms/step)')
    print('No training performed. Phase 2 needs its own concurrent PPO benchmark.')


if __name__ == '__main__':
    main()
