"""Evaluation uses deterministic actions, fixed grid starts and unmodified physics."""
from pathlib import Path
from .env import RacingEnv
from .policy import Driver


def evaluate(checkpoint: Path, episodes: int = 3, should_stop=lambda:False) -> dict:
    driver=Driver(checkpoint)
    env=RacingEnv(driver.car_id,driver.track_id,training=False)
    times=[]; attempted=0; failures={}
    try:
        for episode in range(episodes):
            if should_stop():
                break
            raw,_=env.reset(seed=episode,options={'evaluation_variant':episode})
            attempted+=1
            while True:
                if should_stop():
                    attempted-=1
                    break
                raw,_,terminated,truncated,info=env.step(driver.action(raw))
                if terminated or truncated:
                    times.extend(info['lap_times'])
                    if not info['lap_times']:
                        failures[info['reason']]=failures.get(info['reason'],0)+1
                    break
    finally:
        driver.close(); env.close()
    return {'best_lap':min(times) if times else None,
            'mean_lap':sum(times)/len(times) if times else None,
            'completion_rate':len(times)/attempted if attempted else 0.,
            'completed_laps':len(times),'episodes':attempted,'failures':failures}
