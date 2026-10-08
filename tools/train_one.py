"""Internal worker entry point; normally started through train_all."""
from pathlib import Path
import sys
if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gt_academy.rl.runtime import configure_environment
configure_environment()

if __name__=='__main__':
    from gt_academy.rl.training import main
    main()
