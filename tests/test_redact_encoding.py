from scan_for_secrets.scanner import redact_file


def test_redact_preserves_non_utf8_bytes(tmp_path):
    target = tmp_path / "notes.txt"
    # latin-1 encoded content: secret plus a non-UTF-8 byte (0xe9 = "é")
    target.write_bytes("password hunter2 and caf\xe9\n".encode("latin-1"))
    count = redact_file(target, ["hunter2"])
    assert count == 1
    assert target.read_bytes() == "password REDACTED and caf\xe9\n".encode("latin-1")
