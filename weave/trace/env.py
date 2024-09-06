import os
import configparser

WEAVE_PARALLELISM = "WEAVE_PARALLELISM"


class Settings:
    """A minimal readonly implementation of wandb/old/settings.py for reading settings"""

    DEFAULT_SECTION = "default"
    DEFAULT_BASE_URL = "https://api.wandb.ai"

    def __init__(self) -> None:
        self._settings = configparser.ConfigParser()
        if not self._settings.has_section(self.DEFAULT_SECTION):
            self._settings.add_section(self.DEFAULT_SECTION)
        self._settings.read([Settings._global_path(), Settings._local_path()])

    @property
    def base_url(self) -> str:
        try:
            return self._settings.get(self.DEFAULT_SECTION, "base_url")
        except configparser.NoOptionError:
            return self.DEFAULT_BASE_URL

    @staticmethod
    def _local_path() -> str:
        return os.path.join(os.getcwd(), "wandb", "settings")

    @staticmethod
    def _global_path() -> str:
        default_config_dir = os.path.join(os.path.expanduser("~"), ".config", "wandb")
        config_dir = os.environ.get("WANDB_CONFIG_DIR", default_config_dir)
        return os.path.join(config_dir, "settings")


def get_weave_parallelism() -> int:
    return int(os.getenv(WEAVE_PARALLELISM, "20"))


def wandb_production() -> bool:
    return os.getenv("WEAVE_ENV") == "wandb_production"


def wandb_base_url() -> str:
    settings = Settings()
    return os.environ.get("WANDB_BASE_URL", settings.base_url).rstrip("/")


def wandb_frontend_base_url() -> str:
    public_url = os.getenv("WANDB_PUBLIC_BASE_URL", "").rstrip("/")
    return public_url if public_url != "" else wandb_base_url()


def weave_trace_server_url() -> str:
    base_url = wandb_frontend_base_url()
    default = "https://trace.wandb.ai"
    if base_url != "https://api.wandb.ai":
        default = base_url + "/traces"
    return os.getenv("WF_TRACE_SERVER_URL", default)
