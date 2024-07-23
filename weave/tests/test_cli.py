from click.testing import CliRunner

from weave.cli import cli
from weave.version import VERSION


def test_version():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert result.output == f"cli, version {VERSION}\n"
