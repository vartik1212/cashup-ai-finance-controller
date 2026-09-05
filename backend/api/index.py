"""
Vercel Serverless Function entrypoint for FastAPI backend.
Exports the FastAPI `app` instance.
"""
import sys
from pathlib import Path
import types

# Ensure backend root directory is in sys.path
_backend_dir = Path(__file__).parent.parent.resolve()
if str(_backend_dir) in sys.path:
    sys.path.remove(str(_backend_dir))
sys.path.insert(0, str(_backend_dir))

# Ensure 'backend' module alias is in sys.modules for any submodule imports
if "backend" not in sys.modules:
    _backend_pkg = types.ModuleType("backend")
    _backend_pkg.__path__ = [str(_backend_dir)]
    sys.modules["backend"] = _backend_pkg

from main import app
