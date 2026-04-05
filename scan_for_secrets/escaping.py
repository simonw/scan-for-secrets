import json
import urllib.parse


def _json_escaped(secret: str) -> str:
    """JSON string escaping: \\", \\\\, \\n, \\t, \\uXXXX etc."""
    return json.dumps(secret)[1:-1]


def _url_encoded(secret: str) -> str:
    """Full percent-encoding of all characters."""
    return urllib.parse.quote(secret, safe="")


def _html_entity_encoded(secret: str) -> str:
    """Replace &, <, >, \" with HTML entities. Non-ASCII as &#xHH;."""
    result = []
    for ch in secret:
        if ch == "&":
            result.append("&amp;")
        elif ch == "<":
            result.append("&lt;")
        elif ch == ">":
            result.append("&gt;")
        elif ch == '"':
            result.append("&quot;")
        elif ord(ch) > 127:
            for byte in ch.encode("utf-8"):
                result.append(f"&#x{byte:02X};")
        else:
            result.append(ch)
    return "".join(result)


def _backslash_doubled(secret: str) -> str:
    """Double every backslash."""
    return secret.replace("\\", "\\\\")


def _unicode_escaped(secret: str) -> str:
    """Python unicode_escape encoding."""
    return secret.encode("unicode_escape").decode("ascii")


def _repr_escaped(secret: str) -> str:
    """Python repr() with outer quotes stripped."""
    r = repr(secret)
    # Strip the outer quotes (could be ' or ")
    return r[1:-1]


def generate_variants(secret: str) -> list[tuple[str, str]]:
    """Generate escaped variants of a secret string.

    Returns a list of (variant_string, encoding_name) tuples.
    The literal is always first. Variants identical to the literal are omitted.
    """
    encoders = [
        ("json", _json_escaped),
        ("url", _url_encoded),
        ("html", _html_entity_encoded),
        ("backslash-doubled", _backslash_doubled),
        ("unicode-escape", _unicode_escaped),
        ("repr", _repr_escaped),
    ]

    variants = [("literal", secret)]
    seen = {secret}

    for name, encoder in encoders:
        encoded = encoder(secret)
        if encoded not in seen:
            variants.append((name, encoded))
            seen.add(encoded)

    # Return as (variant_string, encoding_name) — swap from internal (name, string) order
    return [(s, name) for name, s in variants]
