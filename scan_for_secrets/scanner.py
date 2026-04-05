import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from .escaping import generate_variants

SKIP_DIRS = {".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv"}


@dataclass
class Match:
    file_path: str
    line_number: int
    secret_hint: str
    encoding: str


@dataclass
class ScanResult:
    matches: list[Match] = field(default_factory=list)
    files_scanned: int = 0

    @property
    def has_secrets(self) -> bool:
        return len(self.matches) > 0


def _is_binary_file(file_path: Path) -> bool:
    """Return True if file appears to be binary (contains null bytes in first 8192 bytes)."""
    try:
        chunk = file_path.read_bytes()[:8192]
        return b"\x00" in chunk
    except (OSError, PermissionError):
        return True


def _make_hint(secret: str) -> str:
    """Return first 4 characters of secret followed by '...'."""
    return secret[:4] + "..."


def _prepare_variants(
    secrets: list[str],
) -> list[tuple[str, str, list[tuple[str, str]]]]:
    """Pre-compute escaped variants for each secret."""
    secret_variants = []
    for secret in secrets:
        if not secret:
            continue
        hint = _make_hint(secret)
        variants = generate_variants(secret)
        secret_variants.append((secret, hint, variants))
    return secret_variants


def scan_directory_iter(
    directory: str | Path,
    secrets: list[str],
    on_enter_directory: Callable[[str], None] | None = None,
) -> Iterator[Match]:
    """Yield matches as they are found, streaming results.

    Args:
        directory: Root directory to scan.
        secrets: List of secret strings to search for.
        on_enter_directory: Optional callback invoked with the relative path
            of each directory as it is entered.

    Yields:
        Match objects as secrets are discovered.
    """
    directory = Path(directory)
    secret_variants = _prepare_variants(secrets)
    if not secret_variants:
        return

    for dirpath, dirnames, filenames in os.walk(directory):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

        if on_enter_directory is not None:
            rel_dir = os.path.relpath(dirpath, directory)
            on_enter_directory(rel_dir)

        for filename in filenames:
            file_path = Path(dirpath) / filename
            if _is_binary_file(file_path):
                continue

            rel_path = str(file_path.relative_to(directory))

            try:
                with open(file_path, encoding="utf-8", errors="ignore") as f:
                    for line_number, line in enumerate(f, start=1):
                        for _secret, hint, variants in secret_variants:
                            for variant_string, encoding_name in variants:
                                if variant_string in line:
                                    yield Match(
                                        file_path=rel_path,
                                        line_number=line_number,
                                        secret_hint=hint,
                                        encoding=encoding_name,
                                    )
                                    # Only report the first matching variant per secret per line
                                    break
            except (OSError, PermissionError):
                continue


def scan_directory(directory: str | Path, secrets: list[str]) -> ScanResult:
    """Scan a directory for secrets, checking literal and escaped variants.

    Args:
        directory: Root directory to scan.
        secrets: List of secret strings to search for.

    Returns:
        ScanResult with matches and file count.
    """
    directory = Path(directory)
    result = ScanResult()
    secret_variants = _prepare_variants(secrets)
    if not secret_variants:
        return result

    for dirpath, dirnames, filenames in os.walk(directory):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

        for filename in filenames:
            file_path = Path(dirpath) / filename
            if _is_binary_file(file_path):
                continue

            result.files_scanned += 1
            rel_path = str(file_path.relative_to(directory))

            try:
                with open(file_path, encoding="utf-8", errors="ignore") as f:
                    for line_number, line in enumerate(f, start=1):
                        for _secret, hint, variants in secret_variants:
                            for variant_string, encoding_name in variants:
                                if variant_string in line:
                                    result.matches.append(
                                        Match(
                                            file_path=rel_path,
                                            line_number=line_number,
                                            secret_hint=hint,
                                            encoding=encoding_name,
                                        )
                                    )
                                    # Only report the first matching variant per secret per line
                                    break
            except (OSError, PermissionError):
                continue

    return result
