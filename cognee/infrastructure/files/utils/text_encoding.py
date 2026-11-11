"""
Encoding sniffing for byte samples of text files.

Readers that only see the first N bytes of a file cannot ask the file system for
an encoding, and UTF-16 is the trap: for ASCII-range text half of its bytes are
NUL, so a null-byte heuristic reads a perfectly good text file as binary. Worse,
decoding that sample as UTF-8 turns every character into ``C\\x00o\\x00``, so
regexes over it match nothing.

Detect the byte order mark first — it names the encoding outright — and fall
back to the NUL parity a BOM-less UTF-16 sample leaves behind.
"""

import codecs

# Longest BOM first: a UTF-32 LE BOM starts with the UTF-16 LE one.
_BOMS = (
    (codecs.BOM_UTF32_LE, "utf-32-le"),
    (codecs.BOM_UTF32_BE, "utf-32-be"),
    (codecs.BOM_UTF16_LE, "utf-16-le"),
    (codecs.BOM_UTF16_BE, "utf-16-be"),
    (codecs.BOM_UTF8, "utf-8-sig"),
)

# A byte order mark is the strongest signal, so it wins over any heuristic.
_DEFAULT_ENCODING = "utf-8"

# Characters that are text even though ``str.isprintable`` says otherwise.
_TEXT_CONTROLS = frozenset("\t\n\r\f\v")


def bom_encoding(content: bytes) -> str | None:
    """Return the encoding named by a leading byte order mark, if there is one."""
    for bom, encoding in _BOMS:
        if content.startswith(bom):
            return encoding
    return None


def _printable_ratio(text: str) -> float:
    if not text:
        return 0.0
    printable = sum(1 for char in text if char.isprintable() or char in _TEXT_CONTROLS)
    return printable / len(text)


def _decodes_as_text(content: bytes, encoding: str) -> bool:
    """Whether the sample decodes cleanly in `encoding` and reads as prose."""
    # A sample cut at max_sample_bytes can split the last code unit.
    sample = content[: len(content) - len(content) % 2]
    try:
        text = sample.decode(encoding)
    except UnicodeDecodeError:
        return False
    return _printable_ratio(text) >= 0.9


def utf16_encoding(content: bytes) -> str | None:
    """Return the byte order of BOM-less UTF-16 content, or None if it is not UTF-16.

    ASCII-range UTF-16 puts a NUL in every other byte; which of the two byte
    positions holds the NUL says whether the file is little- or big-endian.
    A decode of the whole sample confirms it, so binary blobs that happen to
    carry NULs are not mistaken for text.
    """
    if len(content) < 4:
        return None

    even_bytes, odd_bytes = content[0::2], content[1::2]
    even_nuls = even_bytes.count(0) / len(even_bytes)
    odd_nuls = odd_bytes.count(0) / len(odd_bytes)

    # NULs scattered over both positions are binary; too few to judge, ignore.
    if min(even_nuls, odd_nuls) > 0.2 or max(even_nuls, odd_nuls) < 0.5:
        return None

    encoding = "utf-16-be" if even_nuls > odd_nuls else "utf-16-le"
    return encoding if _decodes_as_text(content, encoding) else None


def text_encoding(content: bytes) -> str | None:
    """Return the encoding `content` is written in, or None when it is not UTF-16/32 text."""
    return bom_encoding(content) or utf16_encoding(content)


def decode_text_content(content: bytes) -> str:
    """Decode a byte sample of a text file, honouring a UTF-16/32 byte order mark.

    Undecodable bytes are replaced rather than raised: a caller scanning for
    personal data must still see the readable part of the sample.
    """
    encoding = text_encoding(content)
    if encoding is None:
        return content.decode(_DEFAULT_ENCODING, errors="replace")

    text = content.decode(encoding, errors="replace")
    # ``utf-16-le`` and friends keep the BOM as U+FEFF; it is not file content.
    return text[1:] if text.startswith("\ufeff") else text
