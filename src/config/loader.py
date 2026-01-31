"""Configuration loader with Pydantic validation and env var expansion."""

import os
import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel


class SummarizerConfig(BaseModel):
    """Configuration for summarizer backend."""

    backend: Literal["openrouter", "mock"] = "openrouter"
    model: str | None = None
    api_key: str | None = None
    base_url: str | None = None


class HaluGateConfig(BaseModel):
    """Configuration for HaluGate backend (main branch's 3-stage pipeline)."""

    backend: Literal["local", "http", "mock"] = "local"
    use_sentinel: bool = True
    device: str = "cpu"
    url: str | None = None  # For HTTP backend


class OverseerConfig(BaseModel):
    """Configuration for Overseer retry logic."""

    max_retries: int = 2
    groundedness_threshold: float = 0.8


class ProfileConfig(BaseModel):
    """Configuration profile containing all backend configs."""

    summarizer: SummarizerConfig
    halugate: HaluGateConfig
    overseer: OverseerConfig = OverseerConfig()


class ConfigFile(BaseModel):
    """Root configuration file structure."""

    profiles: dict[str, ProfileConfig]


def expand_env_vars(value: str) -> str:
    """Expand ${VAR} or $VAR references in string with environment variables.

    Args:
        value: String potentially containing env var references

    Returns:
        String with env vars expanded
    """
    if not isinstance(value, str):
        return value

    # Replace ${VAR} style references
    pattern = r"\$\{([^}]+)\}"

    def replacer(match):
        var_name = match.group(1)
        return os.environ.get(var_name, match.group(0))

    return re.sub(pattern, replacer, value)


def expand_env_vars_recursive(data):
    """Recursively expand env vars in nested dict/list structures.

    Args:
        data: Dict, list, or primitive value

    Returns:
        Data structure with all env vars expanded
    """
    if isinstance(data, dict):
        return {k: expand_env_vars_recursive(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [expand_env_vars_recursive(item) for item in data]
    elif isinstance(data, str):
        return expand_env_vars(data)
    else:
        return data


def load_config_from_yaml(config_path: Path, profile_name: str) -> ProfileConfig:
    """Load configuration from YAML file.

    Args:
        config_path: Path to config YAML file
        profile_name: Name of profile to load

    Returns:
        ProfileConfig for the requested profile

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValidationError: If config is invalid
        KeyError: If profile doesn't exist
    """
    with open(config_path) as f:
        raw_data = yaml.safe_load(f)

    # Expand environment variables
    expanded_data = expand_env_vars_recursive(raw_data)

    # Validate structure
    config_file = ConfigFile(**expanded_data)

    # Get requested profile
    if profile_name not in config_file.profiles:
        available = ", ".join(config_file.profiles.keys())
        raise KeyError(
            f"Profile '{profile_name}' not found. " f"Available profiles: {available}"
        )

    return config_file.profiles[profile_name]


def load_config_from_env() -> ProfileConfig:
    """Load configuration from environment variables (fallback mode).

    This provides backward compatibility when config file doesn't exist.
    Uses the same env vars as before.

    Returns:
        ProfileConfig constructed from environment variables
    """
    # Summarizer config
    summarizer = SummarizerConfig(
        backend="openrouter",
        model=os.environ.get("OPENROUTER_MODEL", "upstage/solar-pro-3:free"),
        api_key=os.environ.get("OPENROUTER_API_KEY"),
        base_url=os.environ.get(
            "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        ),
    )

    # HaluGate config - default to local for main branch
    halugate = HaluGateConfig(
        backend="local",
        use_sentinel=True,
        device="cpu",
    )

    # Overseer config - use defaults
    overseer = OverseerConfig()

    return ProfileConfig(
        summarizer=summarizer,
        halugate=halugate,
        overseer=overseer,
    )


def load_config(
    profile: str | None = None,
    config_path: Path | None = None,
) -> ProfileConfig:
    """Load configuration from YAML file or environment variables.

    This is the main entry point for loading configuration. It tries to load
    from a YAML config file first, and falls back to environment variables
    if the file doesn't exist (for backward compatibility).

    Args:
        profile: Profile name to load. If None, uses MODEL_PROFILE env var
                or "dev-fast" as default.
        config_path: Path to config file. If None, uses src/config/models.yaml
                    in the project root.

    Returns:
        ProfileConfig with all backend configurations

    Raises:
        ValidationError: If configuration is invalid
        KeyError: If requested profile doesn't exist
    """
    # Determine profile name
    if profile is None:
        profile = os.environ.get("MODEL_PROFILE", "dev-fast")

    # Determine config file path
    if config_path is None:
        project_root = Path(__file__).parent.parent.parent
        config_path = project_root / "src" / "config" / "models.yaml"

    # Try to load from YAML, fall back to env vars
    if config_path.exists():
        try:
            return load_config_from_yaml(config_path, profile)
        except Exception as e:
            print(f"Warning: Failed to load config from {config_path}: {e}")
            print("Falling back to environment variables...")
            return load_config_from_env()
    else:
        print(f"Config file {config_path} not found, using environment variables")
        return load_config_from_env()
