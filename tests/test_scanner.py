import pytest

from scan_for_secrets.scanner import scan_directory, ScanResult, Match


def test_scan_finds_literal_secret(tmp_path):
    (tmp_path / "file.txt").write_text("my secret is sk-abc123xyz\n")
    result = scan_directory(tmp_path, ["sk-abc123xyz"])
    assert result.has_secrets
    assert len(result.matches) == 1
    assert result.matches[0].file_path == "file.txt"


def test_scan_no_match(tmp_path):
    (tmp_path / "file.txt").write_text("nothing interesting here\n")
    result = scan_directory(tmp_path, ["sk-abc123xyz"])
    assert not result.has_secrets
    assert result.matches == []


def test_scan_returns_line_number(tmp_path):
    (tmp_path / "file.txt").write_text("line 1\nline 2\nthe secret sk-abc123xyz is here\nline 4\n")
    result = scan_directory(tmp_path, ["sk-abc123xyz"])
    assert result.matches[0].line_number == 3


def test_scan_returns_relative_path(tmp_path):
    sub = tmp_path / "subdir"
    sub.mkdir()
    (sub / "deep.txt").write_text("secret sk-abc123xyz\n")
    result = scan_directory(tmp_path, ["sk-abc123xyz"])
    assert result.matches[0].file_path == "subdir/deep.txt"


def test_scan_recursive(tmp_path):
    deep = tmp_path / "a" / "b" / "c"
    deep.mkdir(parents=True)
    (deep / "file.txt").write_text("secret sk-abc123xyz\n")
    result = scan_directory(tmp_path, ["sk-abc123xyz"])
    assert result.has_secrets
    assert result.matches[0].file_path == "a/b/c/file.txt"


def test_scan_multiple_secrets(tmp_path):
    (tmp_path / "file.txt").write_text("first secret1 and secret2 here\n")
    result = scan_directory(tmp_path, ["secret1", "secret2"])
    assert len(result.matches) == 2


# --- Skipped directories and binary files ---


@pytest.mark.parametrize(
    "skip_dir",
    [
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        "node_modules",
        ".hg",
        ".svn",
    ],
    ids=lambda d: f"skip-{d}",
)
def test_scan_skips_directory(tmp_path, skip_dir):
    d = tmp_path / skip_dir
    d.mkdir()
    (d / "file.txt").write_text("secret sk-abc123xyz\n")
    result = scan_directory(tmp_path, ["sk-abc123xyz"])
    assert not result.has_secrets


def test_scan_skips_binary_files(tmp_path):
    (tmp_path / "binary.dat").write_bytes(b"secret sk-abc123xyz \x00 more data")
    result = scan_directory(tmp_path, ["sk-abc123xyz"])
    assert not result.has_secrets


# --- Escaped variant detection ---


@pytest.mark.parametrize(
    "secret, file_content, expected_encoding",
    [
        # JSON-escaped: quote in secret appears as \" in file
        ('pass"word', '{"key": "pass\\"word"}\n', "json"),
        # URL-encoded: = and & become %3D and %26
        ("key=val&other", "url=key%3Dval%26other\n", "url"),
        # Backslash-doubled: single \ in secret appears as \\ in file
        ("a\\b", "found a\\\\b here\n", "json"),
    ],
    ids=["json-escaped-quote", "url-encoded", "backslash-doubled"],
)
def test_scan_finds_escaped_variant(tmp_path, secret, file_content, expected_encoding):
    (tmp_path / "file.txt").write_text(file_content)
    result = scan_directory(tmp_path, [secret])
    assert result.has_secrets
    assert result.matches[0].encoding == expected_encoding


# --- Secret hint formatting ---


@pytest.mark.parametrize(
    "secret, expected_hint",
    [
        # Long secret: first 4 chars + "..."
        ("sk-abcdefghijk", "sk-a..."),
        # Short secret (3 chars): still gets "..."
        ("abc", "abc..."),
        # Exactly 4 chars
        ("abcd", "abcd..."),
    ],
    ids=["long-secret", "short-secret", "four-chars"],
)
def test_scan_secret_hint(tmp_path, secret, expected_hint):
    (tmp_path / "file.txt").write_text(f"token {secret}\n")
    result = scan_directory(tmp_path, [secret])
    assert result.matches[0].secret_hint == expected_hint


# --- Metadata and properties ---


def test_scan_files_scanned_count(tmp_path):
    (tmp_path / "a.txt").write_text("hello\n")
    (tmp_path / "b.txt").write_text("world\n")
    result = scan_directory(tmp_path, ["nothere"])
    assert result.files_scanned == 2


def test_scan_empty_directory(tmp_path):
    result = scan_directory(tmp_path, ["secret"])
    assert not result.has_secrets
    assert result.files_scanned == 0


def test_scan_has_secrets_property(tmp_path):
    (tmp_path / "file.txt").write_text("secret here\n")
    result_with = scan_directory(tmp_path, ["secret"])
    result_without = scan_directory(tmp_path, ["nope"])
    assert result_with.has_secrets is True
    assert result_without.has_secrets is False


def test_scan_result_dataclass(tmp_path):
    result = scan_directory(tmp_path, ["x"])
    assert isinstance(result, ScanResult)
    assert isinstance(result.matches, list)
