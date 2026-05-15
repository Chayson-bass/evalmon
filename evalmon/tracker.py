import threading

_config: dict = {
    "enabled": True,
    "judge_model": "claude-haiku-4-5-20251001",
}

_context = threading.local()


def configure(
    enabled: bool = True,
    judge_model: str = "claude-haiku-4-5-20251001",
    db_path: str | None = None,
) -> None:
    """Global configuration. Call once at startup."""
    _config["enabled"] = enabled
    _config["judge_model"] = judge_model
    if db_path:
        from .storage import set_db_path
        set_db_path(db_path)


def set_context(
    prompt_version: str | None = None,
    user_id: str | None = None,
    session_id: str | None = None,
    tags: list[str] | None = None,
) -> None:
    """Attach metadata to every LLM call made after this point in the current thread."""
    _context.prompt_version = prompt_version
    _context.user_id = user_id
    _context.session_id = session_id
    _context.tags = tags


def get_context() -> dict:
    return {
        "prompt_version": getattr(_context, "prompt_version", None),
        "user_id":        getattr(_context, "user_id",        None),
        "session_id":     getattr(_context, "session_id",     None),
        "tags":           getattr(_context, "tags",           None),
    }


def is_enabled() -> bool:
    return _config.get("enabled", True)


def get_judge_model() -> str:
    return _config.get("judge_model", "claude-haiku-4-5-20251001")
