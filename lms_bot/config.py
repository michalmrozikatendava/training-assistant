from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv() -> None:
    env_path = Path(".env")
    if not env_path.exists():
        return

    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv()


@dataclass
class Settings:
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    lms_username: str = os.getenv("LMS_USERNAME", "")
    lms_password: str = os.getenv("LMS_PASSWORD", "")
    headless: bool = os.getenv("HEADLESS", "false").lower() == "true"
    slow_mo_ms: int = int(os.getenv("SLOW_MO_MS", "0"))
    cookies_path: Path = Path(os.getenv("COOKIES_PATH", ".playwright-state.json"))
    default_timeout_ms: int = int(os.getenv("DEFAULT_TIMEOUT_MS", "15000"))
    loop_delay_min_seconds: float = float(os.getenv("LOOP_DELAY_MIN_SECONDS", "1"))
    loop_delay_max_seconds: float = float(os.getenv("LOOP_DELAY_MAX_SECONDS", "3"))
    screenshot_dir: Path = Path(os.getenv("SCREENSHOT_DIR", "artifacts/screenshots"))
    max_steps: int = int(os.getenv("MAX_STEPS", "200"))


settings = Settings()
