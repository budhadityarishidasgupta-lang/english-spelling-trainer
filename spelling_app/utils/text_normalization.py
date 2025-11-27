import unicodedata
from typing import Any

def normalize_word(raw: Any) -> str:
    """
    Normalize a word string so that storage and lookups are consistent.

    Steps:
    - convert to string
    - Unicode normalize to NFC
    - replace common curly quotes with straight ones
    - remove newlines and carriage returns
    - replace tabs with spaces
    - strip leading/trailing whitespace
    - collapse internal whitespace to a single space
    """
    if raw is None:
        return ""

    # 1. string + unicode normalize
    word = unicodedata.normalize("NFC", str(raw))

    # 2. normalize quotes
    word = (
        word.replace("’", "'")
            .replace("‘", "'")
            .replace("“", '"')
            .replace("”", '"')
    )

    # 3. remove line breaks, normalize whitespace
    word = word.replace("\r", "").replace("\n", "")
    word = word.replace("\t", " ")

    # 4. strip + collapse multiple spaces
    word = " ".join(word.strip().split())

    return word
