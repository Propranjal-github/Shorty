from __future__ import annotations

_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
_BASE = len(_ALPHABET)
_INDEX = {char: idx for idx, char in enumerate(_ALPHABET)}


def encode(number: int) -> str:
    """Encode a non-negative integer to a base62 string.

    Runs in O(k) where k is the number of output digits. Inverse of `decode`.
    """
    if number < 0:
        raise ValueError("number must be non-negative")
    if number == 0:
        return _ALPHABET[0]
    chars: list[str] = []
    while number:
        number, rem = divmod(number, _BASE)
        chars.append(_ALPHABET[rem])
    return "".join(reversed(chars))


def decode(text: str) -> int:
    """Decode a base62 string back to an int. Raises ValueError on bad input."""
    if not text:
        raise ValueError("text must be non-empty")
    result = 0
    for char in text:
        idx = _INDEX.get(char)
        if idx is None:
            raise ValueError(f"invalid base62 character: {char!r}")
        result = result * _BASE + idx
    return result
