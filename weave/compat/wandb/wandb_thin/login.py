"""Log in to Weights & Biases.

This authenticates your machine to log data to your account.
"""

from __future__ import annotations

import configparser
import enum
import logging
import os
from pathlib import Path
from typing import Literal

import click

from weave.compat.wandb.util.netrc import Netrc
from weave.compat.wandb.wandb_thin import env
from weave.compat.wandb.wandb_thin.util import app_url

logger = logging.getLogger(__name__)


def _handle_host_wandb_setting(host: str | None) -> None:
    """Write the host parameter to the global settings file.

    This takes the parameter from wandb.login for use by the
    application's APIs.
    """
    if host == "https://api.wandb.ai" or host is None:
        _clear_setting("base_url")
    elif host:
        host = host.rstrip("/")
        _set_setting("base_url", host)


def _set_setting(key: str, value: str) -> None:
    """Set a setting in the wandb settings file."""
    try:
        default_config_dir = Path.home() / ".config" / "wandb"
        config_dir = os.getenv(env.CONFIG_DIR, str(default_config_dir))
        settings_path = Path(config_dir) / "settings"

        # Ensure directory exists
        settings_path.parent.mkdir(parents=True, exist_ok=True)

        settings = configparser.ConfigParser()
        if settings_path.exists():
            settings.read(str(settings_path))

        if not settings.has_section("default"):
            settings.add_section("default")

        settings.set("default", key, value)

        with open(settings_path, "w") as f:
            settings.write(f)
    except Exception as e:
        logger.warning(f"Failed to write setting {key}: {e}")


def _clear_setting(key: str) -> None:
    """Clear a setting from the wandb settings file."""
    try:
        default_config_dir = Path.home() / ".config" / "wandb"
        config_dir = os.getenv(env.CONFIG_DIR, str(default_config_dir))
        settings_path = Path(config_dir) / "settings"

        if not settings_path.exists():
            return

        settings = configparser.ConfigParser()
        settings.read(str(settings_path))

        if settings.has_section("default") and settings.has_option("default", key):
            settings.remove_option("default", key)
            with open(settings_path, "w") as f:
                settings.write(f)
    except Exception as e:
        logger.warning(f"Failed to clear setting {key}: {e}")


def login(
    anonymous: Literal["must", "allow", "never"] | None = None,
    key: str | None = None,
    relogin: bool | None = None,
    host: str | None = None,
    force: bool | None = None,
    timeout: int | None = None,
    verify: bool = False,
    referrer: str | None = None,
) -> bool:
    """Set up W&B login credentials.

    By default, this will only store credentials locally without
    verifying them with the W&B server. To verify credentials, pass
    `verify=True`.

    Args:
        anonymous: (string, optional) Can be "must", "allow", or "never".
            If set to "must", always log a user in anonymously. If set to
            "allow", only create an anonymous user if the user
            isn't already logged in. If set to "never", never log a
            user anonymously. Default set to "never".
        key: (string, optional) The API key to use.
        relogin: (bool, optional) If true, will re-prompt for API key.
        host: (string, optional) The host to connect to.
        force: (bool, optional) If true, will force a relogin.
        timeout: (int, optional) Number of seconds to wait for user input.
        verify: (bool) Verify the credentials with the W&B server.
        referrer: (string, optional) The referrer to use in the URL login request.

    Returns:
        bool: if key is configured

    Raises:
        AuthenticationError - if api_key fails verification with the server
        UsageError - if api_key cannot be configured and no tty
    """
    _handle_host_wandb_setting(host)
    return _login(
        anonymous=anonymous,
        key=key,
        relogin=relogin,
        host=host,
        force=force,
        timeout=timeout,
        verify=verify,
        referrer=referrer,
    )


class ApiKeyStatus(enum.Enum):
    """Status of API key configuration."""

    VALID = 1
    NOTTY = 2
    OFFLINE = 3
    DISABLED = 4


class _WandbLogin:
    """Manages the W&B login process."""

    def __init__(
        self,
        anonymous: Literal["must", "allow", "never"] | None = None,
        force: bool | None = None,
        host: str | None = None,
        key: str | None = None,
        relogin: bool | None = None,
        timeout: int | None = None,
    ):
        """Initialize the login manager.

        Args:
            anonymous: Anonymous login setting.
            force: Force relogin if True.
            host: Host to connect to.
            key: API key to use.
            relogin: If True, will re-prompt for API key.
            timeout: Timeout for user input.
        """
        self._relogin = relogin
        self._force = force
        self._timeout = timeout
        self._key = key
        self._host = host if host else _get_default_host()
        self.is_anonymous = anonymous == "must"

    def is_apikey_configured(self) -> bool:
        """Returns whether an API key is set or can be inferred."""
        if self._key:
            return True

        netrc = Netrc()
        credentials = netrc.get_credentials(self._host)
        return credentials is not None

    def _print_logged_in_message(self) -> None:
        """Prints a message telling the user they are logged in."""
        host_str = f" to {self._host}" if self._host != "api.wandb.ai" else ""
        login_state_str = f"W&B API key is configured{host_str}"
        login_info_str = "Use `wandb login --relogin` to force relogin"
        logger.info(f"{login_state_str}. {login_info_str}")

    def try_save_api_key(self, key: str) -> None:
        """Saves the API key to disk for future use.

        Args:
            key: The API key to save.
        """
        if key:
            try:
                netrc = Netrc()
                netrc.add_or_update_entry(self._host, "user", key)
            except Exception as e:
                logger.warning(f"Failed to save API key: {e}")

    def _prompt_api_key(
        self, referrer: str | None = None
    ) -> tuple[str | None, ApiKeyStatus]:
        """Prompts user for API key.

        Args:
            referrer: Referrer for the login URL.

        Returns:
            Tuple of API key and status.
        """
        url = app_url(f"https://{self._host}")
        authorize_url = f"{url}/authorize?ref={referrer}"
        logger.info("Logging into Weights & Biases")
        logger.info(f"You can find your API key in your browser here: {authorize_url}")
        logger.info("Paste an API key from your profile and hit enter:")

        try:
            api_key = click.prompt(
                "Enter your Weights & Biases API key",
                hide_input=True,
                err=True,
                show_default=False,
            )
            logger.info("")
        except click.Abort:
            return None, ApiKeyStatus.OFFLINE
        except (EOFError, OSError):
            # Handle cases where input is not available (no TTY, EOF, etc.)
            return None, ApiKeyStatus.NOTTY

        try:
            _validate_api_key(api_key)
        except ValueError as e:
            logger.warning("API key validation failed: %s", e)
            return self._prompt_api_key(referrer)

        return api_key, ApiKeyStatus.VALID

    def prompt_api_key(
        self, referrer: str | None = None
    ) -> tuple[str | None, ApiKeyStatus]:
        """Updates the global API key by prompting the user.

        Args:
            referrer: Referrer for the login URL.

        Returns:
            Tuple of API key and status.

        Raises:
            ValueError: If no TTY available for input.
        """
        key, status = self._prompt_api_key(referrer)
        if status == ApiKeyStatus.NOTTY:
            raise ValueError(
                "api_key not configured (no-tty). call wandb.login(key=[your_api_key])"
            )

        return key, status

    def _verify_login(self, key: str) -> None:
        """Verify the API key with the server.

        Args:
            key: The API key to verify.

        Raises:
            ValueError: If API key verification fails.
        """
        # For now, just do basic validation since we don't have server verification
        _validate_api_key(key)


def _login(
    *,
    anonymous: Literal["allow", "must", "never"] | None = None,
    key: str | None = None,
    relogin: bool | None = None,
    host: str | None = None,
    force: bool | None = None,
    timeout: int | None = None,
    verify: bool = False,
    referrer: str | None = None,
    _silent: bool | None = None,
    _disable_warning: bool | None = None,
) -> bool:
    """Internal login implementation.

    Args:
        anonymous: Anonymous login setting.
        key: API key to use.
        relogin: If True, will re-prompt for API key.
        host: Host to connect to.
        force: Force relogin if True.
        timeout: Timeout for user input.
        verify: Verify credentials with server.
        referrer: Referrer for login URL.
        _silent: Internal flag to suppress output.
        _disable_warning: Internal flag to disable warnings.

    Returns:
        bool: True if login successful, False otherwise.
    """
    wlogin = _WandbLogin(
        anonymous=anonymous,
        force=force,
        host=host,
        key=key,
        relogin=relogin,
        timeout=timeout,
    )

    key_status = None
    key_is_pre_configured = False

    if key is None:
        # Check if key is already set in netrc
        netrc = Netrc()
        credentials = netrc.get_credentials(wlogin._host)
        if credentials and not relogin:
            key = credentials["password"]
            key_is_pre_configured = True
        else:
            try:
                key, key_status = wlogin.prompt_api_key(referrer=referrer)
            except ValueError as e:
                logger.warning("Failed to prompt for API key: %s", e)
                return False

    if verify and key:
        try:
            wlogin._verify_login(key)
        except ValueError as e:
            logger.warning("API key verification failed: %s", e)
            return False

    if not key_is_pre_configured and key:
        wlogin.try_save_api_key(key)

    if key and not _silent:
        wlogin._print_logged_in_message()

    return key is not None


def _validate_api_key(api_key: str) -> None:
    """Validate the format of a W&B API key.

    Args:
        api_key (str): The API key to validate.

    Raises:
        ValueError: If the API key format is invalid.

    Examples:
        >>> _validate_api_key("1234567890123456789012345678901234567890")  # Valid
        >>> _validate_api_key("short")  # Raises ValueError
    """
    if "-" in api_key:  # on-prem style
        parts = api_key.split("-")
        key = parts[-1]
    else:  # normal style
        key = api_key

    if len(key) < 40:
        raise ValueError(
            f"API key must be at least 40 characters long, yours was {len(key)}"
        ) from None


def _get_default_host() -> str:
    """Get the default wandb host, checking WANDB_BASE_URL environment variable first.

    Then checks settings file, then falls back to api.wandb.ai.
    This mimics the behavior of the real wandb library to ensure consistency.

    Returns:
        str: The default host to use for W&B API connections.

    Examples:
        >>> _get_default_host()
        'api.wandb.ai'
    """
    # Check environment variable first
    env_base_url = os.getenv(env.BASE_URL)
    if env_base_url:
        env_base_url = env_base_url.rstrip("/")
        # Parse out just the hostname from the URL
        if env_base_url.startswith(("http://", "https://")):
            env_base_url = env_base_url.split("://", 1)[1]
        return env_base_url

    # Check settings file
    settings_host = _get_host_from_settings()
    if settings_host:
        return settings_host

    # Default fallback
    return "api.wandb.ai"


def _get_host_from_settings() -> str | None:
    """Get the host from wandb settings file.

    This checks ~/.config/wandb/settings for a base_url setting.

    Returns:
        str | None: The host from settings file, or None if not found.

    Examples:
        >>> _get_host_from_settings()
        'custom.wandb.server'
    """
    try:
        default_config_dir = Path.home() / ".config" / "wandb"
        config_dir = os.getenv(env.CONFIG_DIR, str(default_config_dir))
        settings_path = Path(config_dir) / "settings"

        if not settings_path.exists():
            return None

        settings = configparser.ConfigParser()
        settings.read(str(settings_path))

        if settings.has_section("default") and settings.has_option(
            "default", "base_url"
        ):
            base_url = settings.get("default", "base_url")
            # Parse out just the hostname from the URL
            if base_url.startswith(("http://", "https://")):
                base_url = base_url.split("://", 1)[1]
            return base_url.rstrip("/")

    except Exception:
        # Silently ignore errors reading settings file
        pass

    return None
