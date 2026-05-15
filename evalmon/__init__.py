def _autoload_env() -> None:
    """Load .env from the project root or CWD automatically on import."""
    try:
        from dotenv import load_dotenv
        from pathlib import Path
        candidates = [
            Path(__file__).parent.parent / ".env",  # package root — most reliable
            Path.cwd() / ".env",
        ]
        for p in candidates:
            if p.exists():
                load_dotenv(p, override=True)
                return
    except ImportError:
        pass  # python-dotenv not installed — user must set env vars manually

_autoload_env()

from .wrapper import wrap
from .tracker import configure, set_context
from .evals import create_eval, run_evals, list_evals, delete_eval, compare_versions
from .alerts import alert_on_regression, check_regression
from .storage import get_db_path

__version__ = "0.1.0"

__all__ = [
    "wrap",
    "configure",
    "set_context",
    "create_eval",
    "run_evals",
    "list_evals",
    "delete_eval",
    "compare_versions",
    "alert_on_regression",
    "check_regression",
    "get_db_path",
]
