import subprocess
import sys
from pathlib import Path

import click

from .scanner import scan_directory_iter


@click.command()
@click.version_option()
@click.argument("secrets", nargs=-1)
@click.option(
    "-d",
    "--directory",
    default=".",
    type=click.Path(exists=True, file_okay=False),
    help="Directory to scan (default: current directory)",
)
@click.option(
    "-c",
    "--config",
    "config_path",
    type=click.Path(exists=True),
    default=None,
    help="Path to a config file that outputs secrets",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Show directories as they are scanned",
)
def cli(secrets, directory, config_path, verbose):
    """Scan text files in a directory for secret strings.

    Pass one or more SECRETS as arguments, pipe them via stdin, or use a config
    file. All text files in the directory are checked for both literal matches
    and common escaped variants (JSON, URL, HTML entities, etc).

    Exits with code 0 if clean, 1 if secrets are found, 2 if no secrets were
    provided. With no arguments or piped input, looks for a default config at
    ~/.scan-for-secrets.conf.sh.

    Config files are executed as shell scripts. Each line of stdout is treated
    as a secret to scan for. Use "echo $ENV_VAR" or any command that outputs
    secrets, one per line. Blank lines are ignored.
    """
    all_secrets = list(secrets)

    # Read from stdin if not a TTY
    stdin = click.get_text_stream("stdin")
    stdin_secrets = []
    if not stdin.isatty():
        for line in stdin:
            line = line.strip()
            if line:
                stdin_secrets.append(line)
        all_secrets.extend(stdin_secrets)

    # Config file handling
    if config_path:
        # -c is always additive
        all_secrets.extend(_run_config(config_path))
    elif not all_secrets:
        # No args and no stdin — try default config
        default_config = Path.home() / ".scan-for-secrets.conf.sh"
        if default_config.exists():
            all_secrets.extend(_run_config(str(default_config)))

    if not all_secrets:
        click.echo(
            "No secrets provided. Pass secrets as arguments, pipe them via stdin, or set up a config file.",
            err=True,
        )
        sys.exit(2)

    def _on_enter_directory(rel_dir: str) -> None:
        click.echo(rel_dir, err=True)

    found = False
    for match in scan_directory_iter(
        directory,
        all_secrets,
        on_enter_directory=_on_enter_directory if verbose else None,
    ):
        click.echo(
            f"{match.file_path}:{match.line_number}: {match.secret_hint} ({match.encoding})"
        )
        found = True

    if found:
        sys.exit(1)


def _run_config(config_path: str) -> list[str]:
    """Execute a config file and return the secrets it outputs.

    If the file starts with a shebang (#!) it is executed directly,
    otherwise it is run with bash.
    """
    with open(config_path) as f:
        first_line = f.readline()
    cmd = [config_path] if first_line.startswith("#!") else ["sh", config_path]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        click.echo(f"Warning: config file error: {e}", err=True)
        return []

    if proc.returncode != 0 and not proc.stdout.strip():
        click.echo(f"Warning: config file exited with code {proc.returncode}", err=True)
        return []

    secrets = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line:
            secrets.append(line)
    return secrets
