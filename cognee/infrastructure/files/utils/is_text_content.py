from cognee.infrastructure.files.utils.text_encoding import bom_encoding, utf16_encoding


def is_text_content(content):
    """
    Determine if the content is text-based.

    This function checks for various indicators of text content, including byte
    order marks (BOMs) and UTF-16 without one, null bytes, ASCII character ranges,
    and common line breaks. If none of these indicators are present, the function
    defaults to assuming the content is text-based.

    Parameters:
    -----------

        - content: The byte content to be checked for text characteristics.

    Returns:
    --------

        - bool: Returns True if the content is determined to be text, False otherwise.
    """
    # Check for common text encodings (BOMs) before the null bytes below: UTF-16
    # and UTF-32 text carries a NUL in half of its bytes, which is not binary.
    if bom_encoding(content):
        return True

    # UTF-16 without a BOM shows the same NUL-in-every-other-byte shape.
    if utf16_encoding(content):
        return True

    # Check for null bytes
    if b"\0" in content:
        return False

    # Check for ASCII characters
    if all(0x20 <= byte <= 0x7E or byte in (b"\n", b"\r", b"\t") for byte in content):
        return True

    # Check for common line break characters
    if b"\n" in content or b"\r" in content:
        return True

    # If no obvious indicators found, assume it's a text file
    return True
