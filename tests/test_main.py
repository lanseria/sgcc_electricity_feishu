from typer.testing import CliRunner
from sgcc_electricity_feishu.main import app
import pytest

runner = CliRunner()

def test_hello():
    result = runner.invoke(app, ["hello"])
    assert result.exit_code == 0
    assert "Hello" in result.stdout

def test_hello_with_name():
    result = runner.invoke(app, ["hello", "--name", "World"])
    assert result.exit_code == 0
    assert "World" in result.stdout
