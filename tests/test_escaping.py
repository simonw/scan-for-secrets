import pytest

from scan_for_secrets.escaping import generate_variants


def _variant_dict(secret):
    """Helper: returns {encoding_name: variant_string} for a secret."""
    return {name: v for v, name in generate_variants(secret)}


def test_literal_always_first():
    variants = generate_variants("sk-abc123")
    assert variants[0] == ("sk-abc123", "literal")


def test_returns_list_of_tuples():
    variants = generate_variants("test")
    for item in variants:
        assert isinstance(item, tuple)
        assert len(item) == 2
        assert isinstance(item[0], str)
        assert isinstance(item[1], str)


@pytest.mark.parametrize(
    "secret, encoding, expected",
    [
        # JSON: double quotes are backslash-escaped
        ('pass"word', "json", 'pass\\"word'),
        # JSON: backslashes are doubled
        ("C:\\Users\\secret", "json", "C:\\\\Users\\\\secret"),
        # JSON: newlines become \n literal
        ("line1\nline2", "json", "line1\\nline2"),
        # JSON: tabs become \t literal
        ("before\tafter", "json", "before\\tafter"),
        # URL: = and & are percent-encoded
        ("key=abc&token=xyz", "url", "key%3Dabc%26token%3Dxyz"),
        # URL: spaces become %20
        ("my secret key", "url", "my%20secret%20key"),
        # URL: forward slashes are encoded
        ("abc/def/ghi", "url", "abc%2Fdef%2Fghi"),
        # HTML: & becomes &amp;
        ("sk&123", "html", "sk&amp;123"),
        # HTML: angle brackets become &lt; and &gt;
        ("<token>", "html", "&lt;token&gt;"),
        # HTML: double quotes become &quot;
        ('say"hello"', "html", "say&quot;hello&quot;"),
        # Unicode escape: non-ASCII é becomes \xe9
        ("café", "unicode-escape", "caf\\xe9"),
    ],
    ids=[
        "json-quotes",
        "json-backslashes",
        "json-newlines",
        "json-tabs",
        "url-equals-ampersand",
        "url-spaces",
        "url-slashes",
        "html-ampersand",
        "html-angle-brackets",
        "html-quotes",
        "unicode-escape-non-ascii",
    ],
)
def test_encoding_produces_expected_variant(secret, encoding, expected):
    d = _variant_dict(secret)
    assert d[encoding] == expected


@pytest.mark.parametrize(
    "secret, expected_in_variants",
    [
        # Backslash doubling: C:\secret\key -> C:\\secret\\key
        # (may be produced by json or backslash-doubled encoder, either is fine)
        ("C:\\secret\\key", "C:\\\\secret\\\\key"),
        # repr/json of newline: actual newline -> \n escape sequence
        ("line1\nline2", "line1\\nline2"),
    ],
    ids=[
        "backslash-doubled-present",
        "repr-newline-present",
    ],
)
def test_variant_string_is_present(secret, expected_in_variants):
    """Check that a specific variant string appears, regardless of which encoder produced it."""
    variant_strings = [v for v, _ in generate_variants(secret)]
    assert expected_in_variants in variant_strings


def test_backslash_doubled_not_present_when_no_backslashes():
    # Plain secret with no backslashes — variant identical to literal, deduplicated out
    d = _variant_dict("simplesecret")
    assert "backslash-doubled" not in d


def test_deduplication_no_duplicate_strings():
    # For plain ASCII with no special chars, many encodings produce identical
    # output and should be deduplicated
    variants = generate_variants("simplesecret123")
    variant_strings = [v for v, _ in variants]
    assert len(variant_strings) == len(set(variant_strings))


def test_deduplication_keeps_distinct_variants():
    # a&b=c has special chars that differ across encoding schemes
    d = _variant_dict("a&b=c")
    assert d["literal"] == "a&b=c"
    assert d["url"] == "a%26b%3Dc"
    assert d["html"] == "a&amp;b=c"
