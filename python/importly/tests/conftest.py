import sys
from pathlib import Path

# Shared fake Importly API for the unit tests (integrations/python/_testing).
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_testing"))
