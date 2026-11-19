def count_tokens(text: str) -> int:
    """Return a conservative token estimate without network-fetched vocabularies.

    UTF-8 byte count is an upper bound for the byte-fallback tokenization used by
    the configured embedding tokenizer, so monthly reservations cannot be
    undercounted. It may reject unusually non-ASCII documents earlier than an
    exact tokenizer would.
    """
    return len(text.encode("utf-8"))
