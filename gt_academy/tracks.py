"""Closed cubic B-spline tracks, resampled uniformly for bounded local queries.

B-splines approximate the hand-placed points rather than interpolating them.
This deliberately rounds hairpins and removes curvature spikes at joins.
"""
from dataclasses import dataclass
import numpy as np
from .config import TRACK, SENSORS


@dataclass(frozen=True)
class TrackSpec:
    name: str
    target_length: float
    width: float
    color: tuple
    points: tuple
    character: str


SPECS = (
    TrackSpec('Sunrise Oval', 1200, 16, (157, 139, 114),
              ((-180,-75),(-80,-100),(45,-100),(80,-70),(120,-100),(185,-55),
               (190,60),(80,100),(-100,95),(-185,40)),
              'A forgiving club circuit with a braking chicane and a long sweeper.'),
    TrackSpec('Hairpin Valley', 1600, 13, (120, 145, 128),
              ((-200,-120),(180,-120),(230,-70),(180,-20),(-90,-20),(-140,30),(-90,80),
               (180,80),(230,130),(180,185),(-210,185),(-250,100),(-250,-50)),
              'Three hairpins, short straights and traction zones.'),
    TrackSpec('Esses Run', 1800, 14, (123, 144, 159),
              ((-240,-120),(-155,-175),(-70,-40),(30,-185),(120,-40),(205,-150),
               (290,-20),(240,120),(135,60),(40,170),(-60,50),(-165,170),(-285,55)),
              'Flowing S-curves and rhythm changes.'),
    TrackSpec('Longshot Speedway', 2400, 15, (157, 151, 132),
              ((-420,-100),(-200,-110),(80,-110),(130,-60),(180,-110),(370,-110),
               (460,-60),(460,40),(375,85),(100,85),(-160,85),(-220,140),(-300,85),
               (-440,150),(-500,65),(-490,-25)),
              'Long straights interrupted by two braking chicanes.'),
    TrackSpec('Grand Circuit', 3200, 13, (113, 124, 129),
              ((-280,-220),(-80,-230),(100,-220),(280,-180),(310,-100),(250,-50),
               (140,-70),(90,-20),(160,35),(280,60),(300,160),(170,240),(0,220),
               (-90,150),(-180,210),(-300,150),(-330,40),(-220,-10),(-240,-95),(-330,-130)),
              'A chicane, tightening turns and a long sweeper.'),
)


def spline(points: np.ndarray) -> np.ndarray:
    t = np.arange(TRACK.spline_samples, dtype=float) / TRACK.spline_samples
    weights = np.array(((1-t)**3, 3*t**3-6*t*t+4,
                        -3*t**3+3*t*t+3*t+1, t**3)).T / 6
    return np.concatenate([weights @ points[(np.arange(4)+i-1) % len(points)]
                           for i in range(len(points))])


class Track:
    def __init__(self, spec: TrackSpec):
        self.spec = spec
        dense = spline(np.asarray(spec.points, dtype=float))
        dense = np.vstack((dense, dense[0]))
        distances = np.r_[0., np.cumsum(np.linalg.norm(np.diff(dense, axis=0), axis=1))]
        dense *= spec.target_length / distances[-1]
        distances *= spec.target_length / distances[-1]
        self.count = round(spec.target_length / TRACK.spacing)
        samples = np.linspace(0, distances[-1], self.count, endpoint=False)
        self.center = np.column_stack([np.interp(samples, distances, dense[:, axis]) for axis in (0,1)])
        self.segments = np.roll(self.center, -1, axis=0) - self.center
        self.segment_lengths = np.linalg.norm(self.segments, axis=1)
        self.distance = np.r_[0., np.cumsum(self.segment_lengths)]
        self.length = float(self.distance[-1])
        self.tangent = self.segments / self.segment_lengths[:, None]
        smooth_tangent = np.roll(self.center, -1, axis=0) - np.roll(self.center, 1, axis=0)
        smooth_tangent /= np.linalg.norm(smooth_tangent, axis=1)[:, None]
        self.normal = np.column_stack((-smooth_tangent[:, 1], smooth_tangent[:, 0]))
        theta = np.arctan2(smooth_tangent[:, 1], smooth_tangent[:, 0])
        turn = (np.roll(theta, -1) - np.roll(theta, 1) + np.pi) % (2*np.pi) - np.pi
        self.curvature = turn / (2 * self.length / self.count)
        half = spec.width / 2
        self.left = self.center + self.normal * half
        self.right = self.center - self.normal * half
        self.left_wall = self.center + self.normal * (half + TRACK.runoff)
        self.right_wall = self.center - self.normal * (half + TRACK.runoff)
        self.kerb_left = self.curvature > TRACK.kerb_curvature
        self.kerb_right = self.curvature < -TRACK.kerb_curvature
        self.gates = np.linspace(0, self.length, TRACK.gates, endpoint=False)
        # Ray and straight-distance work is bounded/precomputed, independent of track length.
        straight_steps = int(SENSORS.straight_range / TRACK.spacing)
        self.straight = np.zeros(self.count)
        for k in range(straight_steps, -1, -1):
            curved = np.abs(np.roll(self.curvature, -k)) > SENSORS.straight_curvature
            self.straight = np.where(curved, k * TRACK.spacing, self.straight)
        no_turn = np.ones(self.count, dtype=bool)
        for k in range(straight_steps + 1):
            no_turn &= np.abs(np.roll(self.curvature, -k)) <= SENSORS.straight_curvature
        self.straight[no_turn] = SENSORS.straight_range
        self.validate()
        for value in vars(self).values():
            if isinstance(value, np.ndarray):
                value.flags.writeable = False

    def nearest(self, x: float, y: float, hint: int | None = None) -> tuple[int, float, float]:
        """Return segment, signed left offset and arclength. Full search only at spawn."""
        indices = (np.arange(self.count) if hint is None else
                   (np.arange(-TRACK.nearest_window, TRACK.nearest_window+1) + hint) % self.count)
        relative = np.array((x,y)) - self.center[indices]
        vectors = self.segments[indices]
        fraction = np.clip(np.einsum('ij,ij->i', relative, vectors) / self.segment_lengths[indices]**2, 0, 1)
        residual = relative - fraction[:,None] * vectors
        squared = np.einsum('ij,ij->i', residual, residual)
        selected = int(np.argmin(squared))
        # At a vertex either incident segment can be equally near. Resolve
        # ties by absolute index so local and full searches agree at the seam.
        ties = np.flatnonzero(squared <= squared[selected] + 1e-10)
        if len(ties) > 1:
            selected = int(ties[np.argmin(indices[ties])])
        index = int(indices[selected])
        tangent = self.tangent[index]
        offset = float(tangent[0]*residual[selected,1] - tangent[1]*residual[selected,0])
        progress = (self.distance[index] + fraction[selected]*self.segment_lengths[index]) % self.length
        return index, offset, float(progress)

    def nearest_many(self, points: np.ndarray, hint: int) -> tuple[np.ndarray,np.ndarray,np.ndarray]:
        """Batch wheel/hull queries to amortise NumPy dispatch in the hot path."""
        indices = (np.arange(-TRACK.nearest_window,TRACK.nearest_window+1)+hint) % self.count
        relative = points[:,None,:]-self.center[indices][None,:,:]
        vectors = self.segments[indices]
        fraction = np.clip(np.einsum('kij,ij->ki',relative,vectors)/self.segment_lengths[indices]**2,0,1)
        residual = relative-fraction[:,:,None]*vectors[None,:,:]
        squared = np.einsum('kij,kij->ki',residual,residual)
        # Minimum absolute segment index breaks equal-distance vertex ties.
        minimum = np.min(squared,axis=1)
        chosen = np.argmin(np.where(squared <= minimum[:,None]+1e-10,indices[None,:],self.count),axis=1)
        row = np.arange(len(points))
        index = indices[chosen]
        tangent = self.tangent[index]
        offset = tangent[:,0]*residual[row,chosen,1]-tangent[:,1]*residual[row,chosen,0]
        progress = (self.distance[index]+fraction[row,chosen]*self.segment_lengths[index])%self.length
        return index,offset,progress

    def at(self, distance: float) -> tuple[np.ndarray, float, int]:
        distance %= self.length
        i = min(int(np.searchsorted(self.distance, distance, side='right') - 1), self.count-1)
        p = self.center[i] + self.tangent[i] * (distance-self.distance[i])
        return p, float(np.arctan2(self.tangent[i,1], self.tangent[i,0])), i

    def grid(self, slot: int = 0) -> tuple[np.ndarray, float, int]:
        p, heading, i = self.at(-slot * TRACK.grid_spacing)
        if slot:
            p = p + self.normal[i] * (self.spec.width / 5) * (1 if slot % 2 else -1)
        return p, heading, i

    def validate(self) -> None:
        assert abs(self.length / self.spec.target_length - 1) < TRACK.length_tolerance, self.spec.name
        assert np.max(self.segment_lengths) < TRACK.spacing * 1.05, 'Unclosed or uneven centerline'
        assert np.max(np.abs(self.curvature)) * (self.spec.width/2 + TRACK.runoff) < 1, 'Offset curve folds'
        # Broad corridor test catches crossings AND close nonadjacent parallel pieces.
        stride = TRACK.validation_stride
        points = self.center[::stride]
        ids = np.arange(0, self.count, stride)
        along = np.abs(self.distance[ids,None] - self.distance[ids][None,:])
        along = np.minimum(along, self.length-along)
        width = self.spec.width + 2*TRACK.runoff
        separation = np.linalg.norm(points[:,None,:]-points[None,:,:], axis=2)
        assert not np.any((along > width*2) & (separation < width)), 'Track corridors overlap'


TRACKS = tuple(Track(spec) for spec in SPECS)
