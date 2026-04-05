# scan-for-secrets

[![PyPI](https://img.shields.io/pypi/v/scan-for-secrets.svg)](https://pypi.org/project/scan-for-secrets/)
[![Changelog](https://img.shields.io/github/v/release/simonw/scan-for-secrets?include_prereleases&label=changelog)](https://github.com/simonw/scan-for-secrets/releases)
[![Tests](https://github.com/simonw/scan-for-secrets/actions/workflows/test.yml/badge.svg)](https://github.com/simonw/scan-for-secrets/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/simonw/scan-for-secrets/blob/master/LICENSE)

Scan for secrets in files you want to publish

## Installation

Install this tool using `pip`:
```bash
pip install scan-for-secrets
```
Or `uv`:
```bash
uv tool install scan-for-secrets
```
Or use without installing via `uvx`:
```bash
uvx scan-for-secrets --help
```

## Usage

This tool helps scan all of the files in a directory to see if they include specified secret strings. For example, run this if you want to publish the logs from a coding agent session after first confirming no secrets from environment variables are exposed in those logs.

Basic usage looks like this:
```bash
scan-for-secrets $OPENAI_API_KEY $ANTHROPIC_API_KEY
```
This will scan text files in the current folder and all sub-folders looking for the values that were passed as positional arguments, including common escaping schemes that might mean a direct string match misses them.

To scan for a secret that can be accessed using another command, use `$(command)` syntax:
```bash
scan-for-secrets "$(llm keys get openai)"
```
Add `-d/--directory` to specify a different directory to scan:
```bash
scan-for-secrets $OPENAI_API_KEY -d ~/my-project
```
You can also pipe a list of newline-separated secrets to the tool:
```bash
cat secrets.txt | scan-for-secrets
```
This can be combined with secrets passed as positional arguments.

## Configuration file

If you run `scan-for-secrets` without any extra arguments or piped data the command will look for a default configuration file to tell it what to scan for instead.

This file lives at `~/.scan-for-secrets.conf.sh` and contains commands that will be executed to retrieve secrets. Each line should be a shell command that outputs a single secret to stdout (or a blank line or a comment).

```bash
# API keys
echo $OPENAI_API_KEY
echo $ANTHROPIC_API_KEY

# AWS (using xargs to strip whitespace)
awk -F= '/aws_secret_access_key/{print $2}' ~/.aws/credentials | xargs

# 1Password
op read "op://Vault/API Key/password"

# LLM keys
llm keys get gemini
```

Blank lines and lines starting with `#` are ignored. The entire file will be executed as a shell script, so you can even use a shebang line at the top to write your configuration in a different language.

With a configuration file setup you can run `scan-for-secrets` like this:

```bash
cd agent-logs/
scan-for-secrets
```
Or this:
```bash
scan-for-secrets -d agent-logs
```
You can also pass a path to a configuration file using the `-c/--config` option:

```bash
scan-for-secrets -c scan.sh
```
Unlike the default configuration behavior, this `-c` option will be combined with any piped data or additional positional arguments.

## Help

For help, run:
```bash
scan-for-secrets --help
```
You can also use:
```bash
python -m scan_for_secrets --help
```

## Development

To contribute to this tool, first checkout the code. Then run the tests:
```bash
cd scan-for-secrets
uv run pytest
```
To run the development version of the command itself:
```bash
uv run scan-for-secrets --help
```
