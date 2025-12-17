"""Tests for config.py - global and local configuration management."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


class TestReadConfig:
    """Tests for _read_config function."""

    def test_returns_default_when_file_not_exists(self):
        """Should return default config when file doesn't exist."""
        from weave.integrations.claude_plugin.config import _read_config

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"
            with patch("weave.integrations.claude_plugin.config.CONFIG_FILE", config_file):
                result = _read_config()
                assert result == {"enabled": False}

    def test_reads_existing_config(self):
        """Should read existing config file."""
        from weave.integrations.claude_plugin.config import _read_config

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"
            config_file.write_text('{"enabled": true, "project": "test/proj"}')

            with patch("weave.integrations.claude_plugin.config.CONFIG_FILE", config_file):
                result = _read_config()
                assert result == {"enabled": True, "project": "test/proj"}

    def test_returns_default_on_invalid_json(self):
        """Should return default config on invalid JSON."""
        from weave.integrations.claude_plugin.config import _read_config

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"
            config_file.write_text("not valid json")

            with patch("weave.integrations.claude_plugin.config.CONFIG_FILE", config_file):
                result = _read_config()
                assert result == {"enabled": False}


class TestWriteConfig:
    """Tests for _write_config function."""

    def test_creates_directory_and_writes_config(self):
        """Should create directory and write config atomically."""
        from weave.integrations.claude_plugin.config import _write_config

        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "subdir"
            config_file = config_dir / "config.json"

            with patch("weave.integrations.claude_plugin.config.CONFIG_DIR", config_dir):
                with patch("weave.integrations.claude_plugin.config.CONFIG_FILE", config_file):
                    _write_config({"enabled": True, "project": "my/project"})

                    assert config_file.exists()
                    content = json.loads(config_file.read_text())
                    assert content == {"enabled": True, "project": "my/project"}


class TestGetEnabled:
    """Tests for get_enabled function."""

    def test_returns_false_by_default(self):
        """Should return False when no config exists."""
        from weave.integrations.claude_plugin.config import get_enabled

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"
            with patch("weave.integrations.claude_plugin.config.CONFIG_FILE", config_file):
                assert get_enabled() is False

    def test_returns_true_when_enabled(self):
        """Should return True when enabled in config."""
        from weave.integrations.claude_plugin.config import get_enabled

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"
            config_file.write_text('{"enabled": true}')

            with patch("weave.integrations.claude_plugin.config.CONFIG_FILE", config_file):
                assert get_enabled() is True


class TestSetEnabled:
    """Tests for set_enabled function."""

    def test_enables_tracing(self):
        """Should set enabled to True."""
        from weave.integrations.claude_plugin.config import get_enabled, set_enabled

        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            config_file = config_dir / "config.json"

            with patch("weave.integrations.claude_plugin.config.CONFIG_DIR", config_dir):
                with patch("weave.integrations.claude_plugin.config.CONFIG_FILE", config_file):
                    set_enabled(True)
                    assert get_enabled() is True

    def test_disables_tracing(self):
        """Should set enabled to False."""
        from weave.integrations.claude_plugin.config import get_enabled, set_enabled

        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            config_file = config_dir / "config.json"
            config_file.write_text('{"enabled": true}')

            with patch("weave.integrations.claude_plugin.config.CONFIG_DIR", config_dir):
                with patch("weave.integrations.claude_plugin.config.CONFIG_FILE", config_file):
                    set_enabled(False)
                    assert get_enabled() is False


class TestGetLocalEnabled:
    """Tests for get_local_enabled function."""

    def test_returns_none_when_no_settings_file(self):
        """Should return None when no local settings file exists."""
        from weave.integrations.claude_plugin.config import get_local_enabled

        with tempfile.TemporaryDirectory() as tmpdir:
            result = get_local_enabled(tmpdir)
            assert result is None

    def test_returns_none_when_key_not_present(self):
        """Should return None when weave.enabled key doesn't exist."""
        from weave.integrations.claude_plugin.config import get_local_enabled

        with tempfile.TemporaryDirectory() as tmpdir:
            settings_dir = Path(tmpdir) / ".claude"
            settings_dir.mkdir()
            settings_file = settings_dir / "settings.json"
            settings_file.write_text('{"other": "value"}')

            result = get_local_enabled(tmpdir)
            assert result is None

    def test_returns_true_when_enabled(self):
        """Should return True when weave.enabled is true."""
        from weave.integrations.claude_plugin.config import get_local_enabled

        with tempfile.TemporaryDirectory() as tmpdir:
            settings_dir = Path(tmpdir) / ".claude"
            settings_dir.mkdir()
            settings_file = settings_dir / "settings.json"
            settings_file.write_text('{"weave": {"enabled": true}}')

            result = get_local_enabled(tmpdir)
            assert result is True

    def test_returns_false_when_disabled(self):
        """Should return False when weave.enabled is false."""
        from weave.integrations.claude_plugin.config import get_local_enabled

        with tempfile.TemporaryDirectory() as tmpdir:
            settings_dir = Path(tmpdir) / ".claude"
            settings_dir.mkdir()
            settings_file = settings_dir / "settings.json"
            settings_file.write_text('{"weave": {"enabled": false}}')

            result = get_local_enabled(tmpdir)
            assert result is False


class TestIsEnabled:
    """Tests for is_enabled function (priority-based check)."""

    def test_local_override_takes_priority(self):
        """Local settings should override global config."""
        from weave.integrations.claude_plugin.config import is_enabled

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create local settings that enable
            settings_dir = Path(tmpdir) / ".claude"
            settings_dir.mkdir()
            settings_file = settings_dir / "settings.json"
            settings_file.write_text('{"weave": {"enabled": true}}')

            # Global config would say disabled
            config_dir = Path(tmpdir) / "global"
            config_dir.mkdir()
            config_file = config_dir / "config.json"
            config_file.write_text('{"enabled": false}')

            with patch("weave.integrations.claude_plugin.config.CONFIG_FILE", config_file):
                result = is_enabled(tmpdir)
                assert result is True

    def test_falls_back_to_global_when_no_local(self):
        """Should use global config when no local override exists."""
        from weave.integrations.claude_plugin.config import is_enabled

        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            config_file = config_dir / "config.json"
            config_file.write_text('{"enabled": true}')

            with patch("weave.integrations.claude_plugin.config.CONFIG_FILE", config_file):
                result = is_enabled(tmpdir)
                assert result is True


class TestSetLocalEnabled:
    """Tests for set_local_enabled function."""

    def test_creates_settings_and_enables(self):
        """Should create settings file and enable weave."""
        from weave.integrations.claude_plugin.config import get_local_enabled, set_local_enabled

        with tempfile.TemporaryDirectory() as tmpdir:
            set_local_enabled(True, tmpdir)
            assert get_local_enabled(tmpdir) is True

    def test_disables_in_existing_settings(self):
        """Should disable weave in existing settings."""
        from weave.integrations.claude_plugin.config import get_local_enabled, set_local_enabled

        with tempfile.TemporaryDirectory() as tmpdir:
            settings_dir = Path(tmpdir) / ".claude"
            settings_dir.mkdir()
            settings_file = settings_dir / "settings.json"
            settings_file.write_text('{"weave": {"enabled": true}}')

            set_local_enabled(False, tmpdir)
            assert get_local_enabled(tmpdir) is False


class TestGetStatus:
    """Tests for get_status function."""

    def test_returns_status_dict(self):
        """Should return status dictionary."""
        from weave.integrations.claude_plugin.config import get_status

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"
            with patch("weave.integrations.claude_plugin.config.CONFIG_FILE", config_file):
                result = get_status(tmpdir)
                assert "global" in result
                assert "local" in result
                assert "effective" in result


class TestHasLocalSettings:
    """Tests for has_local_settings function."""

    def test_returns_false_when_no_settings(self):
        """Should return False when no .claude/settings.json."""
        from weave.integrations.claude_plugin.config import has_local_settings

        with tempfile.TemporaryDirectory() as tmpdir:
            result = has_local_settings(tmpdir)
            assert result is False

    def test_returns_true_when_settings_exist(self):
        """Should return True when .claude/settings.json exists."""
        from weave.integrations.claude_plugin.config import has_local_settings

        with tempfile.TemporaryDirectory() as tmpdir:
            settings_dir = Path(tmpdir) / ".claude"
            settings_dir.mkdir()
            settings_file = settings_dir / "settings.json"
            settings_file.write_text("{}")

            result = has_local_settings(tmpdir)
            assert result is True
