import os
import stat
import sys

from click.testing import CliRunner

from scan_for_secrets.cli import cli


def test_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Scan text files in a directory for secret strings" in result.output



def test_no_secrets_no_config_exits_with_error(tmp_path, monkeypatch):
    # Point HOME at an empty tmp dir so no real ~/.scan-for-secrets.conf.sh is found
    monkeypatch.setenv("HOME", str(tmp_path))
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, [])
        assert result.exit_code == 2
        assert "No secrets" in result.output


def test_scan_clean_exit_0():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("file.txt", "w") as f:
            f.write("nothing interesting here\n")
        result = runner.invoke(cli, ["sk-abc123xyz"])
        assert result.exit_code == 0
        assert result.output == ""


def test_scan_found_exit_1():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("file.txt", "w") as f:
            f.write("my key is sk-abc123xyz\n")
        result = runner.invoke(cli, ["sk-abc123xyz"])
        assert result.exit_code == 1


def test_output_format():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("file.txt", "w") as f:
            f.write("line 1\n")
            f.write("token sk-abc123xyz here\n")
        result = runner.invoke(cli, ["sk-abc123xyz"])
        assert result.exit_code == 1
        assert "file.txt:2" in result.output
        assert "sk-a..." in result.output
        assert "literal" in result.output


def test_directory_option(tmp_path):
    (tmp_path / "secret.txt").write_text("sk-abc123xyz\n")
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["sk-abc123xyz", "-d", str(tmp_path)])
        assert result.exit_code == 1
        assert "secret.txt" in result.output


def test_stdin_secrets():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("file.txt", "w") as f:
            f.write("my key is sk-abc123xyz\n")
        result = runner.invoke(cli, [], input="sk-abc123xyz\n")
        assert result.exit_code == 1
        assert "sk-a..." in result.output


def test_stdin_combined_with_args():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("file.txt", "w") as f:
            f.write("first secret1\nsecond secret2\n")
        result = runner.invoke(cli, ["secret1"], input="secret2\n")
        assert result.exit_code == 1
        assert "secr..." in result.output
        # Both secrets should be found
        lines = result.output.strip().split("\n")
        assert len(lines) == 2


def test_config_file(tmp_path):
    config = tmp_path / "config.sh"
    config.write_text("echo sk-abc123xyz\n")
    config.chmod(config.stat().st_mode | stat.S_IEXEC)

    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("file.txt", "w") as f:
            f.write("key is sk-abc123xyz\n")
        result = runner.invoke(cli, ["-c", str(config)])
        assert result.exit_code == 1
        assert "sk-a..." in result.output


def test_config_additive_with_args(tmp_path):
    config = tmp_path / "config.sh"
    config.write_text("echo secret_from_config\n")
    config.chmod(config.stat().st_mode | stat.S_IEXEC)

    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("file.txt", "w") as f:
            f.write("has secret_from_args and secret_from_config\n")
        result = runner.invoke(cli, ["secret_from_args", "-c", str(config)])
        assert result.exit_code == 1
        lines = result.output.strip().split("\n")
        assert len(lines) == 2


def test_config_file_multiple_secrets(tmp_path):
    config = tmp_path / "config.sh"
    config.write_text("echo secret_one\necho secret_two\n")
    config.chmod(config.stat().st_mode | stat.S_IEXEC)

    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("file.txt", "w") as f:
            f.write("has secret_one here\n")
        result = runner.invoke(cli, ["-c", str(config)])
        assert result.exit_code == 1
        assert "secr..." in result.output


def test_default_config_file(tmp_path, monkeypatch):
    # Create a default config file in a fake home directory
    config = tmp_path / ".scan-for-secrets.conf.sh"
    config.write_text("echo sk-default-secret\n")
    config.chmod(config.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("HOME", str(tmp_path))

    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("file.txt", "w") as f:
            f.write("has sk-default-secret\n")
        result = runner.invoke(cli, [])
        assert result.exit_code == 1
        assert "sk-d..." in result.output


def test_config_file_python_shebang(tmp_path):
    # Config file written in Python with a shebang line
    config = tmp_path / "config.py"
    config.write_text(
        f"#!{sys.executable}\n"
        "print('py-secret-one')\n"
        "print('py-secret-two')\n"
    )
    config.chmod(config.stat().st_mode | stat.S_IEXEC)

    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("file.txt", "w") as f:
            f.write("found py-secret-one and py-secret-two here\n")
        result = runner.invoke(cli, ["-c", str(config)])
        assert result.exit_code == 1
        assert "py-s..." in result.output
        lines = result.output.strip().split("\n")
        assert len(lines) == 2


def test_multiple_files_in_output():
    runner = CliRunner()
    with runner.isolated_filesystem():
        os.makedirs("sub")
        with open("a.txt", "w") as f:
            f.write("sk-abc123xyz\n")
        with open("sub/b.txt", "w") as f:
            f.write("sk-abc123xyz\n")
        result = runner.invoke(cli, ["sk-abc123xyz"])
        assert result.exit_code == 1
        assert "a.txt:1" in result.output
        assert "sub/b.txt:1" in result.output
