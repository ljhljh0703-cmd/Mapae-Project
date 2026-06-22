"""
Mapae (마패) - AI Powered Game Policy Auditor
==============================================

Configuration Loader Module

Loads config from .env (python-dotenv) → config.txt → environment variables.
Priority: env vars > .env > config.txt.

Author: Portfolio Project
License: MIT
Version: 1.1.0
"""

import os
from typing import Dict, Optional
from pathlib import Path

try:
    from dotenv import load_dotenv
    _DOTENV_AVAILABLE = True
except ImportError:
    _DOTENV_AVAILABLE = False


class Config:
    """Configuration manager for Mapae application."""

    def __init__(self, config_file: str = "config.txt"):
        self.config_file = config_file
        self.settings: Dict[str, str] = {}
        self._load_config()

    def _load_config(self):
        """Load configuration: .env → config.txt, then override with env vars."""
        config_path = Path(self.config_file)

        # 1. Load .env if present (does not override existing env vars)
        if _DOTENV_AVAILABLE:
            env_path = config_path.parent / ".env"
            if env_path.exists():
                load_dotenv(env_path, override=False)

        # 2. Load config.txt (key=value pairs)
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, value = line.split("=", 1)
                        self.settings[key.strip()] = value.strip()

        # 3. Environment variables override config.txt
        for key in list(self.settings.keys()):
            env_val = os.getenv(key)
            if env_val:
                self.settings[key] = env_val

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get configuration value. Returns None for placeholders."""
        value = self.settings.get(key) or os.getenv(key, default)
        if value and (value.startswith("your-") or value == "***REMOVED_API_KEY***"):
            return default
        return value

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get boolean configuration value."""
        value = self.get(key)
        if value is None:
            return default
        return value.lower() in ("true", "yes", "1", "on")
