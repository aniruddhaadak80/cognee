"""UTF-16 text is text, not binary.

A UTF-16 file holds a NUL in every other byte for ASCII-range content, so the
plain null-byte heuristic presort used read a Notepad "Unicode" note as binary
and ``detect_pii`` never opened it (issue #6563). The BOM has to win over the
null-byte check, and BOM-less UTF-16 has to be recognised from the same shape.
"""

import codecs

import pytest

from cognee.infrastructure.files.utils.is_text_content import is_text_content
from cognee.infrastructure.files.utils.text_encoding import (
    bom_encoding,
    decode_text_content,
    text_encoding,
    utf16_encoding,
)

TEXT = "Contact: jane.doe@example.com\n"

UTF16_VARIANTS = {
    "utf-16-le-bom": codecs.BOM_UTF16_LE + TEXT.encode("utf-16-le"),
    "utf-16-be-bom": codecs.BOM_UTF16_BE + TEXT.encode("utf-16-be"),
    "utf-16-le-no-bom": TEXT.encode("utf-16-le"),
    "utf-16-be-no-bom": TEXT.encode("utf-16-be"),
}


@pytest.mark.parametrize("variant", UTF16_VARIANTS)
def test_utf16_samples_are_text(variant):
    assert is_text_content(UTF16_VARIANTS[variant])


@pytest.mark.parametrize("variant", UTF16_VARIANTS)
def test_utf16_samples_decode_to_the_original_text(variant):
    assert decode_text_content(UTF16_VARIANTS[variant]) == TEXT


@pytest.mark.parametrize(
    "variant, encoding",
    [
        ("utf-16-le-bom", "utf-16-le"),
        ("utf-16-be-bom", "utf-16-be"),
        ("utf-16-le-no-bom", "utf-16-le"),
        ("utf-16-be-no-bom", "utf-16-be"),
    ],
)
def test_utf16_encoding_is_named(variant, encoding):
    assert text_encoding(UTF16_VARIANTS[variant]) == encoding


def test_utf32_bom_is_text_and_decodes():
    content = codecs.BOM_UTF32_LE + TEXT.encode("utf-32-le")
    assert bom_encoding(content) == "utf-32-le"
    assert is_text_content(content)
    assert decode_text_content(content) == TEXT


def test_utf8_bom_is_stripped():
    content = codecs.BOM_UTF8 + TEXT.encode("utf-8")
    assert is_text_content(content)
    assert decode_text_content(content) == TEXT


def test_plain_utf8_is_unchanged():
    assert text_encoding(TEXT.encode("utf-8")) is None
    assert decode_text_content(TEXT.encode("utf-8")) == TEXT


def test_undecodable_bytes_are_replaced_not_raised():
    # A binary file mislabelled .txt still yields a scannable sample.
    assert "Contact" in decode_text_content(b"Contact: \xff\xfe\x00binary")


def test_binary_content_is_still_binary():
    # PNG signature plus a body of NULs: NULs on both byte positions.
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    assert utf16_encoding(png) is None
    assert not is_text_content(png)


def test_utf16_detection_needs_more_than_a_nul_run():
    # An all-NUL body is not UTF-16 text: both positions are NUL.
    assert utf16_encoding(b"\x00" * 32) is None
    assert not is_text_content(b"\x00" * 32)
