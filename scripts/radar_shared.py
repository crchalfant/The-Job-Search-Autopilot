from __future__ import annotations

import json
import os
import re
from datetime import date
from typing import Any

TITLE_CLEANUP_RE = re.compile(
    r"\s*[-–|]\s*(remote|remote,?\s*(us|usa)?|hybrid|onsite|on-site"
    r"|united states?|us|usa|\w{2,3},\s*\w{2})\s*$",
    re.IGNORECASE,
)

LOCATION_WORDS = {
    "remote", "us", "usa", "united states", "nationwide", "anywhere",
    "hybrid", "onsite", "on-site", "contract", "full-time", "full time",
    "part-time", "part time",
}

SENSITIVE_PROFILE_PREFIXES = (
    "name:",
    "current role:",
    "previous:",
    "education:",
)


def normalize_title(title: str) -> str:
    t = (title or "").lower().strip()
    t = TITLE_CLEANUP_RE.sub("", t).strip()
    t = re.sub(
        r"\(([^)]*)\)",
        lambda m: "" if m.group(1).strip().lower() in LOCATION_WORDS else m.group(0),
        t,
    ).strip()
    for sep in (" - ", " | "):
        if sep in t:
            parts = t.split(sep)
            suffix_words = {w for w in re.split(r"[\s,]+", parts[-1]) if w}
            if suffix_words and suffix_words.issubset(LOCATION_WORDS):
                t = sep.join(parts[:-1]).strip()
    return re.sub(r"\s+", " ", t).strip()


def make_job_id(job: dict[str, Any]) -> str:
    company = str(job.get("company") or "").strip().lower()
    title = normalize_title(str(job.get("title") or ""))
    return f"{company}|{title}"


def sanitize_profile(profile: str) -> str:
    lines = []
    for raw_line in (profile or "").splitlines():
        stripped = raw_line.strip()
        lower = stripped.lower()
        if any(lower.startswith(prefix) for prefix in SENSITIVE_PROFILE_PREFIXES):
            continue
        lines.append(raw_line)
    cleaned = "\n".join(lines).strip()
    return cleaned or (profile or "").strip()


def validate_user_config(cfg: Any) -> None:
    if not isinstance(getattr(cfg, "MIN_SALARY", None), int) or cfg.MIN_SALARY <= 0:
        raise ValueError("MIN_SALARY must be a positive integer")
    for attr in ("VACATION_START", "VACATION_END"):
        if not isinstance(getattr(cfg, attr, None), date):
            raise ValueError(f"{attr} must be a datetime.date")
    if cfg.VACATION_END < cfg.VACATION_START:
        raise ValueError("VACATION_END cannot be earlier than VACATION_START")
    if not isinstance(getattr(cfg, "PROFILE", None), str) or not cfg.PROFILE.strip():
        raise ValueError("PROFILE must be a non-empty string")
    if not isinstance(getattr(cfg, "LOCAL_METRO_TERMS", None), (set, frozenset)) or not cfg.LOCAL_METRO_TERMS:
        raise ValueError("LOCAL_METRO_TERMS must be a non-empty set")
    if not all(isinstance(term, str) and term.strip() for term in cfg.LOCAL_METRO_TERMS):
        raise ValueError("LOCAL_METRO_TERMS must only contain non-empty strings")
    if not isinstance(getattr(cfg, "QUOTES", None), list) or not cfg.QUOTES:
        raise ValueError("QUOTES must be a non-empty list")
    if not all(isinstance(q, str) and q.strip() for q in cfg.QUOTES):
        raise ValueError("QUOTES must only contain non-empty strings")
    query_attrs = [name for name in dir(cfg) if name.endswith("_QUERIES")]
    for name in query_attrs:
        value = getattr(cfg, name)
        if not isinstance(value, list) or not value:
            raise ValueError(f"{name} must be a non-empty list")
        for item in value:
            if isinstance(item, str):
                if not item.strip():
                    raise ValueError(f"{name} must not contain empty strings")
            elif isinstance(item, tuple):
                if not item or not all(isinstance(part, str) and part.strip() for part in item):
                    raise ValueError(f"{name} tuples must only contain non-empty strings")
            elif isinstance(item, dict):
                if not item:
                    raise ValueError(f"{name} must not contain empty dicts")
                for k, v in item.items():
                    if not isinstance(k, str) or not k.strip():
                        raise ValueError(f"{name} dict keys must be non-empty strings")
                    if isinstance(v, str) and not v.strip():
                        raise ValueError(f"{name} dict values must not contain empty strings")
            else:
                raise ValueError(f"{name} contains unsupported entry type: {type(item).__name__}")


def safe_json_load(path: str, *, default: Any, expected_type: type | tuple[type, ...] | None = None) -> Any:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return default
    if expected_type is not None and not isinstance(data, expected_type):
        return default
    return data


def atomic_write_json(path: str, data: Any, *, indent: int = 2) -> None:
    dirpath = os.path.dirname(path)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent)
    os.replace(tmp, path)
