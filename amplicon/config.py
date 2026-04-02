"""
Amplicon Configuration Management

Simple configuration class for centralizing common settings.
Maintains full backward compatibility with existing code.
"""

import os
from dataclasses import dataclass


@dataclass
class AmpliconConfig:
    """Central configuration for Amplicon agent.

    All settings are optional and have sensible defaults.
    API keys are still read from environment variables to maintain
    compatibility with existing .env file structure.

    Usage:
        # Create config with defaults
        config = AmpliconConfig()

        # Override specific settings
        config = AmpliconConfig(llm="gpt-4", timeout_seconds=1200)

        # Modify after creation
        config.path = "./custom_data"
    """

    # Data and execution settings
    path: str = "./data"
    timeout_seconds: int = 600

    # LLM settings (API keys still from environment)
    llm: str = "claude-sonnet-4-5"
    temperature: float = 0.7

    # Tool settings
    use_tool_retriever: bool = True

    # Data licensing settings
    commercial_mode: bool = False  # If True, excludes non-commercial datasets

    # Custom model settings (for custom LLM serving)
    base_url: str | None = None
    api_key: str | None = None  # Only for custom models, not provider API keys

    # LLM source (auto-detected if None)
    source: str | None = None

    # Third-party integrations
    protocols_io_access_token: str | None = None

    # Token and prompt logging settings
    log_tokens: bool = False
    logs_dir: str = "./logs"

    def __post_init__(self):
        """Load any environment variable overrides if they exist."""
        # Check for environment variable overrides (optional)
        # Support both old and new names for backwards compatibility
        if os.getenv("AMPLICON_PATH") or os.getenv("AMPLICON_DATA_PATH"):
            self.path = os.getenv("AMPLICON_PATH") or os.getenv("AMPLICON_DATA_PATH")
        if os.getenv("AMPLICON_TIMEOUT_SECONDS"):
            self.timeout_seconds = int(os.getenv("AMPLICON_TIMEOUT_SECONDS"))
        if os.getenv("AMPLICON_LLM") or os.getenv("AMPLICON_LLM_MODEL"):
            self.llm = os.getenv("AMPLICON_LLM") or os.getenv("AMPLICON_LLM_MODEL")
        if os.getenv("AMPLICON_USE_TOOL_RETRIEVER"):
            self.use_tool_retriever = os.getenv("AMPLICON_USE_TOOL_RETRIEVER").lower() == "true"
        if os.getenv("AMPLICON_COMMERCIAL_MODE"):
            self.commercial_mode = os.getenv("AMPLICON_COMMERCIAL_MODE").lower() == "true"
        if os.getenv("AMPLICON_TEMPERATURE"):
            self.temperature = float(os.getenv("AMPLICON_TEMPERATURE"))
        if os.getenv("AMPLICON_CUSTOM_BASE_URL"):
            self.base_url = os.getenv("AMPLICON_CUSTOM_BASE_URL")
        if os.getenv("AMPLICON_CUSTOM_API_KEY"):
            self.api_key = os.getenv("AMPLICON_CUSTOM_API_KEY")
        if os.getenv("AMPLICON_SOURCE"):
            self.source = os.getenv("AMPLICON_SOURCE")

        # Protocols.io access token (prefer specific env vars)
        env_token = os.getenv("PROTOCOLS_IO_ACCESS_TOKEN") or os.getenv("AMPLICON_PROTOCOLS_IO_ACCESS_TOKEN")
        if env_token:
            self.protocols_io_access_token = env_token

        # Token and prompt logging settings
        if os.getenv("AMPLICON_LOG_TOKENS"):
            self.log_tokens = os.getenv("AMPLICON_LOG_TOKENS").lower() == "true"
        if os.getenv("AMPLICON_LOGS_DIR"):
            self.logs_dir = os.getenv("AMPLICON_LOGS_DIR")

    def to_dict(self) -> dict:
        """Convert config to dictionary for easy access."""
        return {
            "path": self.path,
            "timeout_seconds": self.timeout_seconds,
            "llm": self.llm,
            "temperature": self.temperature,
            "use_tool_retriever": self.use_tool_retriever,
            "commercial_mode": self.commercial_mode,
            "base_url": self.base_url,
            "api_key": self.api_key,
            "source": self.source,
            "log_tokens": self.log_tokens,
            "logs_dir": self.logs_dir,
        }


# Global default config instance (optional, for convenience)
default_config = AmpliconConfig()
