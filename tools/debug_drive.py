"""Launch the Phase 1 driving laboratory."""
from pathlib import Path
import sys

if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from gt_academy.game.debug_viewer import main

if __name__=='__main__':
    main()
