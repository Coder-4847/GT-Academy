"""Human-readable CLI selections map to the fixed five-by-five model grid."""
from ..cars import CARS
from ..tracks import TRACKS
from .storage import slug


def select_ids(value: str, names: list[str]) -> list[int]:
    if value.lower()=='all':
        return list(range(len(names)))
    result=[]
    for word in value.split(','):
        word=word.strip()
        if word.isdigit() and 1<=int(word)<=len(names):
            index=int(word)-1
        else:
            matches=[i for i,name in enumerate(names) if slug(name)==slug(word)]
            if not matches:
                raise ValueError(f'Unknown selection {word!r}; choose '+', '.join(names))
            index=matches[0]
        if index not in result:
            result.append(index)
    if not result:
        raise ValueError('Select at least one item')
    return result


def pairs(cars: str, tracks: str) -> list[tuple[int,int]]:
    car_ids=select_ids(cars,[c.name for c in CARS])
    track_ids=select_ids(tracks,[t.spec.name for t in TRACKS])
    return [(car,track) for track in track_ids for car in car_ids]
