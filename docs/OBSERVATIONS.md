# Frozen interface candidate

The observation layout is retained from Phase 1 and used by the Phase 2 environment and policy loader. It becomes frozen when real training begins. Use `gt_academy.sim.observation(state, car, track)` for both training and inference. It returns a fresh, finite NumPy float32 array of shape `(32,)` and never mutates state. Each policy action lasts four physics ticks by default; this frequency and the environment/reward definitions are covered by the simulation hash.

| Indices | Values | Normalisation |
| --- | --- | --- |
| 0–10 | Asphalt edge rays, -100° through +100° relative to heading | Distance / 70 m, [0,1] |
| 11 | Body forward velocity | / 85 m/s |
| 12 | Body lateral velocity, positive left | / 25 m/s |
| 13 | Yaw rate, positive counterclockwise | / 2.5 rad/s |
| 14 | Actual steering angle | / car's nominal steering lock |
| 15 | Actual throttle actuator | [0,1] |
| 16 | Actual brake actuator | [0,1] |
| 17–18 | Front and rear slip angles | / 0.8 rad |
| 19 | Lateral offset, positive left of centerline | / half asphalt width |
| 20 | Heading minus local tangent heading, wrapped | / pi |
| 21–22 | Clearance to left and right asphalt edges | / full asphalt width |
| 23–26 | Curvature 10, 20, 40 and 70 m ahead | / 0.05 m⁻¹ |
| 27 | Distance until curvature exceeds 0.004 m⁻¹, capped at 300 m | / 300 m |
| 28–31 | Front-right, front-left, rear-right, rear-left on asphalt | +1 asphalt; -1 kerb or grass |

The final array is clipped to [-1,1]. Distances past an edge can therefore be negative for the corresponding clearance. Rays are zero when the car centre is outside the asphalt. Future training uses this exact builder, including its clipping.

Actions are `(steering, throttle_brake)`, shape `(2,)`, bounded to [-1,1]. Positive steering turns left in a world coordinate system with positive Y up. Positive pedal accelerates; negative pedal brakes. Finite out-of-range values are clipped. Nonfinite or malformed actions raise `ValueError`. Steering, throttle and brake are rate limited in the simulation; drivers cannot bypass those limits.

`Simulation.step(action)` advances exactly 1/60 second. `state.ticks` is the authoritative elapsed-tick count. `state.wall_contact` and `state.impact_speed` aggregate all collisions in that tick. `lap.completed_this_step` lasts one tick. Client code owns its own render clock and must not pass variable frame durations into the simulation.
