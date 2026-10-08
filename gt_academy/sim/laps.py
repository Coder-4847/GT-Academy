"""Ordered gates with forward crossings and continuous on-course progress."""
from ..config import PHYSICS, TRACK
from ..tracks import Track
from .state import LapState


def update_lap(lap: LapState, track: Track, progress: float, offset: float,
               dt: float = PHYSICS.dt) -> None:
    lap.completed_this_step = False
    lap.elapsed += dt
    delta = (progress-lap.previous_progress+track.length/2) % track.length-track.length/2
    if abs(delta) > TRACK.max_progress_step:
        lap.valid = False
        lap.invalid_reason = 'Skipped distance / teleport'
    if abs(offset) > track.spec.width/2 + TRACK.kerb_width:
        lap.valid = False
        lap.invalid_reason = 'Left the racing surface'
    lap.distance += delta
    # A gate is an ordered forward crossing in arclength; bounded displacement
    # and corridor validation prevent crossing an unrelated branch or skipping gates.
    if 0 < delta <= TRACK.max_progress_step:
        for gate in (lap.next_gate, 0):
            gate_s = float(track.gates[gate])
            crossing = (gate_s-lap.previous_progress) % track.length
            if crossing < 1e-8:
                crossing = track.length
            if crossing <= delta + 1e-8:
                fraction = crossing/delta
                crossing_offset = lap.previous_offset + fraction*(offset-lap.previous_offset)
                if abs(crossing_offset) > track.spec.width/2:
                    lap.valid = False
                    lap.invalid_reason = 'Missed gate'
                if gate == 0:
                    if lap.next_gate == 0 and lap.valid and lap.distance >= track.length-TRACK.max_progress_step:
                        time = lap.elapsed - dt*(1-fraction)
                        lap.lap_times.append(time)
                        lap.best = time if lap.best is None else min(lap.best,time)
                        lap.completed_this_step = True
                    lap.elapsed = dt*(1-fraction)
                    lap.next_gate = 1
                    lap.valid = abs(crossing_offset) <= track.spec.width/2
                    lap.invalid_reason = '' if lap.valid else 'Missed start gate'
                    lap.distance = delta-crossing
                    break
                if gate == lap.next_gate:
                    lap.next_gate = (lap.next_gate+1) % TRACK.gates
    lap.previous_progress = progress
    lap.previous_offset = offset
