# Plan: Implement scan-for-secrets

## Context
The README describes a tool that scans directories for secret strings (API keys, etc.) in text files, checking both literal matches and common escaped variants. The project skeleton exists but has only placeholder code. We need to build the full tool using TDD with `uv run pytest`.

## Architecture

Three modules, built in dependency order:

1. **`scan_for_secrets/escaping.py`** — Pure functions to generate escaped variants of a secret
2. **`scan_for_secrets/scanner.py`** — Core scanning logic + dataclasses (the Python library API)
3. **`scan_for_secrets/cli.py`** — Rewrite from click.group() to click.command()

## TDD Order (red/green for each round)

### Round 1: Escaping (`escaping.py`)

Write `tests/test_escaping.py` first, then implement.

`generate_variants(secret: str) -> list[tuple[str, str]]` returns `(variant_string, encoding_name)` tuples. Encoding variants:

- **literal** — the secret itself
- **json** — `json.dumps(secret)[1:-1]` (handles `\"`, `\\`, `\n`, `\t`, `\uXXXX`)
- **url** — `urllib.parse.quote(secret, safe="")` 
- **html** — `&amp;`, `&lt;`, `&gt;`, `&quot;`, `&#xHH;` for non-ASCII
- **backslash-doubled** — every `\` → `\\`
- **unicode-escape** — Python `unicode_escape` codec
- **repr** — `repr(secret)` with outer quotes stripped

Deduplicate: skip variants identical to literal. Literal is always first.

### Round 2: Scanner (`scanner.py`)

Write `tests/test_scanner.py` first, then implement.

```python
@dataclass
class Match:
    file_path: str      # relative to scan root
    line_number: int
    secret_hint: str    # first 4 chars + "..."
    encoding: str       # variant name

@dataclass
class ScanResult:
    matches: list[Match]
    files_scanned: int
    
    @property
    def has_secrets(self) -> bool:
        return len(self.matches) > 0

def scan_directory(directory: str | Path, secrets: list[str]) -> ScanResult:
    ...
```

Key behaviors:
- Recursive walk, skip `.git`, `.hg`, `.svn`, `node_modules`, `__pycache__`, `.venv`, `venv`
- Skip binary files (null byte in first 8192 bytes)
- Read files line-by-line with `encoding="utf-8", errors="ignore"`
- Check each line for each variant using `in` operator
- `secret_hint`: first 4 chars of original secret + `"..."`

### Round 3: CLI (`cli.py`)

Write `tests/test_cli.py` first, then implement.

```python
@click.command()
@click.version_option()
@click.argument("secrets", nargs=-1)
@click.option("-d", "--directory", default=".", type=click.Path(exists=True, file_okay=False))
@click.option("-c", "--config", "config_path", type=click.Path(exists=True), default=None)
def cli(secrets, directory, config_path):
```

Secret sources (collected in order):
1. Positional args
2. Stdin (if not a TTY) — newline-separated
3. Config file: `-c` is always additive; default `~/.scan-for-secrets.conf.sh` only when no args and no stdin

Config execution: `subprocess.run(["bash", config_path], capture_output=True, text=True)`

Exit codes: 0 = clean, 1 = secrets found, 2 = no secrets provided (error)

Output format per match: `{file_path}:{line_number}: {secret_hint} ({encoding})`

### Round 4: Library exports

Update `scan_for_secrets/__init__.py` to export `scan_directory`, `ScanResult`, `Match`.

Update `tests/test_scan_for_secrets.py` version assertion (will change from `cli, version` to `scan-for-secrets, version`).

## Files to create/modify

| File | Action |
|------|--------|
| `tests/test_escaping.py` | Create |
| `scan_for_secrets/escaping.py` | Create |
| `tests/test_scanner.py` | Create |
| `scan_for_secrets/scanner.py` | Create |
| `tests/test_cli.py` | Create |
| `scan_for_secrets/cli.py` | Rewrite |
| `scan_for_secrets/__init__.py` | Update exports |
| `tests/test_scan_for_secrets.py` | Fix version test |

## Verification

After each round: `uv run pytest` — all tests green.

Final check: `uv run scan-for-secrets --help` and manual test creating a temp dir with a secret in a file.
