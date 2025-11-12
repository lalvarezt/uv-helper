"""Configuration management for UV-Helper."""

import logging
import os
import tomllib
from pathlib import Path

import tomli_w
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .utils import ensure_dir, expand_path

logger = logging.getLogger(__name__)


class Config(BaseModel):
    """Configuration for UV-Helper.

    Pydantic model that automatically validates configuration values,
    including path expansion and constraint checking.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    repo_dir: Path
    install_dir: Path
    state_file: Path
    clone_depth: int = Field(default=1, ge=1, description="Git clone depth (must be >= 1)")
    auto_symlink: bool = True
    verify_after_install: bool = True
    auto_chmod: bool = True
    use_exact_flag: bool = True

    @field_validator("repo_dir", "install_dir", "state_file", mode="before")
    @classmethod
    def expand_paths(cls, v: str | Path) -> Path:
        """Expand path strings with ~ and environment variables."""
        if isinstance(v, str):
            return expand_path(v)
        return v

    def save(self, path: Path) -> None:
        """
        Save configuration to TOML file using Pydantic serialization.

        Args:
            path: Path to save config file
        """
        ensure_dir(path.parent)

        # Convert to TOML-friendly dictionary structure
        data = {
            "paths": {
                "repo_dir": str(self.repo_dir),
                "install_dir": str(self.install_dir),
                "state_file": str(self.state_file),
            },
            "git": {
                "clone_depth": self.clone_depth,
            },
            "install": {
                "auto_symlink": self.auto_symlink,
                "verify_after_install": self.verify_after_install,
                "auto_chmod": self.auto_chmod,
                "use_exact_flag": self.use_exact_flag,
            },
        }

        with open(path, "wb") as f:
            tomli_w.dump(data, f)


def get_config_path() -> Path:
    """
    Get configuration file path.

    Priority:
    1. UV_HELPER_CONFIG environment variable
    2. Default: ~/.config/uv-helper/config.toml

    Returns:
        Path to config file
    """
    env_config = os.environ.get("UV_HELPER_CONFIG")
    if env_config:
        return expand_path(env_config)

    return expand_path("~/.config/uv-helper/config.toml")


def create_default_config() -> Config:
    """
    Create default configuration.

    Returns:
        Config instance with default values
    """
    return Config(
        repo_dir=expand_path("~/.local/share/uv-helper"),
        install_dir=expand_path("~/.local/bin"),
        state_file=expand_path("~/.local/share/uv-helper/state.json"),
    )


def load_config(config_path: Path | None = None) -> Config:
    """
    Load configuration from TOML file using Pydantic validation.

    Args:
        config_path: Optional custom config path

    Returns:
        Config instance with validated values

    Raises:
        FileNotFoundError: If config file doesn't exist at specified path
        ValueError: If config validation fails
    """
    if config_path is None:
        config_path = get_config_path()

    if config_path.exists():
        # Load TOML file
        with open(config_path, "rb") as f:
            data = tomllib.load(f)

        # Flatten TOML structure to match Config model fields
        flat_data = {
            "repo_dir": data.get("paths", {}).get("repo_dir", "~/.local/share/uv-helper"),
            "install_dir": data.get("paths", {}).get("install_dir", "~/.local/bin"),
            "state_file": data.get("paths", {}).get("state_file", "~/.local/share/uv-helper/state.json"),
            "clone_depth": data.get("git", {}).get("clone_depth", 1),
            "auto_symlink": data.get("install", {}).get("auto_symlink", True),
            "verify_after_install": data.get("install", {}).get("verify_after_install", True),
            "auto_chmod": data.get("install", {}).get("auto_chmod", True),
            "use_exact_flag": data.get("install", {}).get("use_exact_flag", True),
        }

        return Config.model_validate(flat_data)

    # Create default config
    config = create_default_config()

    # Save default config for future use
    try:
        config.save(config_path)
    except (OSError, PermissionError) as e:
        # Don't fail if we can't save (e.g., read-only filesystem, permissions)
        # Just use in-memory config
        logger.warning(f"Could not save default config to {config_path}: {e}")

    return config
