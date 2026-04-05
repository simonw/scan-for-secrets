import os
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

    # Pre-compute all variants for all secrets
    secret_variants: list[tuple[str, str, list[tuple[str, str]]]] = []
    for secret in secrets:
        if not secret:
            continue
        hint = _make_hint(secret)
        variants = generate_variants(secret)
        secret_variants.append((secret, hint, variants))

    if not secret_variants:
        return result

    for dirpath, dirnames, filenames in os.walk(directory):
        # Prune skipped directories in-place
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
