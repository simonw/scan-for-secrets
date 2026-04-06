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
        f"#!{sys.executable}\n" "print('py-secret-one')\n" "print('py-secret-two')\n"
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


def test_multiple_directories(tmp_path):
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    dir_a.mkdir()
    dir_b.mkdir()
    (dir_a / "file.txt").write_text("sk-abc123xyz\n")
    (dir_b / "file.txt").write_text("sk-abc123xyz\n")
    runner = CliRunner()
    result = runner.invoke(cli, ["sk-abc123xyz", "-d", str(dir_a), "-d", str(dir_b)])
    assert result.exit_code == 1
    assert "file.txt:1" in result.output
    lines = result.output.strip().split("\n")
    assert len(lines) == 2


def test_file_option(tmp_path):
    (tmp_path / "target.txt").write_text("sk-abc123xyz\n")
    (tmp_path / "other.txt").write_text("sk-abc123xyz\n")
    runner = CliRunner()
    result = runner.invoke(cli, ["sk-abc123xyz", "-f", str(tmp_path / "target.txt")])
    assert result.exit_code == 1
    assert "target.txt:1" in result.output
    # other.txt should not be scanned
    assert "other.txt" not in result.output


def test_file_option_multiple(tmp_path):
    (tmp_path / "a.txt").write_text("sk-abc123xyz\n")
    (tmp_path / "b.txt").write_text("sk-abc123xyz\n")
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["sk-abc123xyz", "-f", str(tmp_path / "a.txt"), "-f", str(tmp_path / "b.txt")],
    )
    assert result.exit_code == 1
    lines = result.output.strip().split("\n")
    assert len(lines) == 2


def test_file_option_nonexistent_silently_ignored(tmp_path):
    (tmp_path / "real.txt").write_text("sk-abc123xyz\n")
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "sk-abc123xyz",
            "-f",
            str(tmp_path / "real.txt"),
            "-f",
            str(tmp_path / "nonexistent.txt"),
        ],
    )
    assert result.exit_code == 1
    assert "real.txt:1" in result.output


def test_file_and_directory_combined(tmp_path):
    dir_a = tmp_path / "dir"
    dir_a.mkdir()
    (dir_a / "in_dir.txt").write_text("sk-abc123xyz\n")
    (tmp_path / "standalone.txt").write_text("sk-abc123xyz\n")
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["sk-abc123xyz", "-d", str(dir_a), "-f", str(tmp_path / "standalone.txt")],
    )
    assert result.exit_code == 1
    assert "in_dir.txt" in result.output
    assert "standalone.txt" in result.output


def test_file_only_no_directory_scan(tmp_path, monkeypatch):
    # When only -f is given, don't scan cwd
    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / "target.txt"
    target.write_text("sk-abc123xyz\n")
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("cwd_file.txt", "w") as f:
            f.write("sk-abc123xyz\n")
        result = runner.invoke(cli, ["sk-abc123xyz", "-f", str(target)])
        assert result.exit_code == 1
        assert "cwd_file.txt" not in result.output
        assert "target.txt" in result.output


def test_verbose_shows_scanning_directories():
    runner = CliRunner()
    with runner.isolated_filesystem():
        os.makedirs("sub/deep")
        os.makedirs("other")
        with open("a.txt", "w") as f:
            f.write("nothing\n")
        with open("sub/b.txt", "w") as f:
            f.write("nothing\n")
        with open("sub/deep/c.txt", "w") as f:
            f.write("nothing\n")
        with open("other/d.txt", "w") as f:
            f.write("nothing\n")
        result = runner.invoke(cli, ["sk-abc123xyz", "-v"])
        assert result.exit_code == 0
        stderr = result.stderr
        lines = stderr.strip().split("\n")
        assert "." in lines
        assert "sub" in lines
        assert "sub/deep" in lines
        assert "other" in lines


def test_verbose_repeats_matches_at_end():
    runner = CliRunner()
    with runner.isolated_filesystem():
        os.makedirs("sub")
        with open("a.txt", "w") as f:
            f.write("sk-abc123xyz\n")
        with open("sub/b.txt", "w") as f:
            f.write("nothing\n")
        result = runner.invoke(cli, ["sk-abc123xyz", "-v"])
        assert result.exit_code == 1
        # Directory listing appears in stderr
        assert "." in result.stderr
        assert "sub" in result.stderr
        # Filter stdout to just the match lines (CliRunner mixes stderr into output)
        match_line = "a.txt:1: sk-a... (literal)"
        match_lines = [l for l in result.output.split("\n") if match_line in l]
        # Should appear twice: once inline, once in the summary
        assert len(match_lines) == 2


def test_verbose_no_summary_when_clean():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("a.txt", "w") as f:
            f.write("nothing\n")
        result = runner.invoke(cli, ["sk-abc123xyz", "-v"])
        assert result.exit_code == 0
        # No match lines in output (only directory names from stderr bleed)
        assert "sk-a..." not in result.output


def test_verbose_not_shown_without_flag():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("a.txt", "w") as f:
            f.write("nothing\n")
        result = runner.invoke(cli, ["sk-abc123xyz"])
        assert result.exit_code == 0
        assert result.stderr == ""


# --- --redact / -r option ---


def test_redact_shows_matches_and_prompts():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("file.txt", "w") as f:
            f.write("my key is sk-abc123xyz\n")
        # Answer "n" to the prompt
        result = runner.invoke(cli, ["sk-abc123xyz", "-r"], input="n\n")
        assert "file.txt:1" in result.output
        assert "sk-a..." in result.output
        # Should show the confirmation prompt
        assert "Replace" in result.output
        # File should be unchanged
        assert open("file.txt").read() == "my key is sk-abc123xyz\n"


def test_redact_confirms_and_rewrites():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("file.txt", "w") as f:
            f.write("my key is sk-abc123xyz\n")
        result = runner.invoke(cli, ["sk-abc123xyz", "-r"], input="y\n")
        assert "file.txt:1" in result.output
        assert "Replaced" in result.output
        assert open("file.txt").read() == "my key is REDACTED\n"


def test_redact_multiple_files():
    runner = CliRunner()
    with runner.isolated_filesystem():
        os.makedirs("sub")
        with open("a.txt", "w") as f:
            f.write("sk-abc123xyz\n")
        with open("sub/b.txt", "w") as f:
            f.write("sk-abc123xyz\n")
        result = runner.invoke(cli, ["sk-abc123xyz", "-r"], input="y\n")
        assert result.exit_code == 0
        assert open("a.txt").read() == "REDACTED\n"
        assert open("sub/b.txt").read() == "REDACTED\n"


def test_redact_no_matches_no_prompt():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("file.txt", "w") as f:
            f.write("nothing interesting\n")
        result = runner.invoke(cli, ["sk-abc123xyz", "-r"])
        assert result.exit_code == 0
        assert "Replace" not in result.output


def test_redact_aborted_exit_code():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("file.txt", "w") as f:
            f.write("sk-abc123xyz\n")
        result = runner.invoke(cli, ["sk-abc123xyz", "-r"], input="n\n")
        # Should exit 1 (secrets found but not redacted)
        assert result.exit_code == 1


def test_redact_escaped_variants():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("file.json", "w") as f:
            f.write('{"key": "pass\\"word"}\n')
        result = runner.invoke(cli, ['pass"word', "-r"], input="y\n")
        assert "Replaced" in result.output
        assert open("file.json").read() == '{"key": "REDACTED"}\n'


def test_redact_url_encoded():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("file.txt", "w") as f:
            f.write("url=key%3Dval%26other\n")
        result = runner.invoke(cli, ["key=val&other", "-r"], input="y\n")
        assert "Replaced" in result.output
        assert open("file.txt").read() == "url=REDACTED\n"


def test_redact_with_directory_option(tmp_path):
    (tmp_path / "secret.txt").write_text("sk-abc123xyz\n")
    runner = CliRunner()
    result = runner.invoke(
        cli, ["sk-abc123xyz", "-r", "-d", str(tmp_path)], input="y\n"
    )
    assert "Replaced" in result.output
    assert (tmp_path / "secret.txt").read_text() == "REDACTED\n"
