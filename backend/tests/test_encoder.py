from __future__ import annotations

import pytest

from app.core.encoder import decode, encode


def test_encode_decode_roundtrip() -> None:
    for number in [0, 1, 10, 61, 62, 63, 12345, 2**40, 2**63 - 1]:
        assert decode(encode(number)) == number


def test_encode_zero_is_single_char() -> None:
    assert encode(0) == "0"


def test_encode_known_values() -> None:
    assert encode(61) == "z"
    assert encode(62) == "10"
    assert encode(63) == "11"


def test_decode_invalid_character() -> None:
    with pytest.raises(ValueError):
        decode("abc!")


def test_decode_empty() -> None:
    with pytest.raises(ValueError):
        decode("")


def test_encode_rejects_negative() -> None:
    with pytest.raises(ValueError):
        encode(-1)


def test_encoded_output_is_url_safe() -> None:
    text = encode(9_876_543_210_987_654)
    assert all(c.isalnum() for c in text)
