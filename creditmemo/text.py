"""
Shared Markdown-text helpers.

The Markdown renderer emits emphasis with ``*``; the .docx renderer has to
remove it before writing a Word run, and so does the table-cell splitter in
:mod:`creditmemo.tables`. Both sides need the same rule for what is an emphasis
marker and what is content, so the rule lives here rather than being written
twice and drifting — which is exactly what happened. Through 0.2.1
``renderers/docx.py`` stripped every ``*`` unconditionally while ``tables.py``
stripped only ``**``, so the same character survived in a Word table cell and
was deleted from a paragraph of the same document::

    markdown : 'EBITDA margin improved 5 * 3 basis points.'
    docx     : 'EBITDA margin improved 5  3 basis points.'
"""
import re

__all__ = ["strip_emphasis"]

#: A paired ``**bold**`` span. The opening marker may not be followed by
#: whitespace and the closing marker may not be preceded by it — CommonMark's
#: left/right-flanking rule, and the reason ``5 ** 3`` is arithmetic and not
#: emphasis.
_BOLD = re.compile(r"\*\*(?!\s)(.+?)(?<!\s)\*\*", re.S)

#: A paired ``*italic*`` span: single asterisks under the same flanking rule,
#: with no asterisk between them. ``5 * 3 * 7`` matches nothing, because each
#: candidate opener is followed by a space.
_ITALIC = re.compile(r"(?<!\*)\*(?!\s)([^*]+?)(?<!\s)\*(?!\*)", re.S)


def strip_emphasis(text: str) -> str:
    """
    Remove paired Markdown emphasis markers; leave an unpaired ``*`` alone.

    A lone asterisk in underwriter prose is content — multiplication, a
    footnote mark, a redaction — and deleting it changes the number the
    Investment Committee reads. Only markers that pair are syntax.

    Where the pairing is ambiguous this preserves the characters rather than
    guessing, which is the safe direction: the worst case is a literal ``*`` in
    the Word document, not a missing digit.
    """
    return _ITALIC.sub(r"\1", _BOLD.sub(r"\1", text))
