"""Vercel Python entrypoint. Loads the FastAPI app from the src package."""

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from comet.web import app as app
