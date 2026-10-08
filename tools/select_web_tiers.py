"""Select browser-tested actors without changing any model, simulation or training file."""
import json
from pathlib import Path
from gt_academy.rl.tiers import choose_tiers


def main():
    catalog_path=Path('web/catalog.json')
    catalog=json.loads(catalog_path.read_text(encoding='utf-8'))
    reports=json.loads(Path('artifacts/web/wasm-races.json').read_text(encoding='utf-8'))
    if len(reports)!=100: raise ValueError('Complete all 100 browser validations before selection')
    models={}; warnings=[]
    for t in range(5):
        for c in range(5):
            candidates=[]
            for report in reports:
                if not report['key'].startswith(f'{t}:{c}:') or len(report['laps'])!=5 or report['dnf']:continue
                row=catalog['models'][report['key']]
                candidates.append(dict(row,checkpoint=row['file'],standing_mean_lap=row['mean_lap'],
                    mean_lap=sum(report['laps'])/5,episodes=5,completion_rate=1.,source_tier=report['key'].split(':')[2],
                    validation=report))
            chosen,notes=choose_tiers(candidates)
            warnings.extend(f'{t}:{c} {note}' for note in notes)
            for tier,row in chosen.items():
                models[f'{t}:{c}:{tier}']={k:v for k,v in row.items() if k not in ('checkpoint','episodes','completion_rate')}
    catalog['models']=models;catalog['tier_warnings']=warnings
    catalog['browser_validation']='Every selected actor completed five continuous laps in the bundled WebAssembly runtime.'
    catalog_path.write_text(json.dumps(catalog,separators=(',',':')),encoding='utf-8')
    Path('artifacts/web/selected-tiers.json').write_text(json.dumps(dict(tiers=100,unique_models=len({m['file'] for m in models.values()}),warnings=warnings),indent=2),encoding='utf-8')
    print(f'Selected 100 browser-validated tiers. {len(warnings)} pace-spacing warnings.')


if __name__=='__main__':main()
