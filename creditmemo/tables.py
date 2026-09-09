"""
Shared Markdown-table helpers.

The Markdown renderer emits pipe tables; the .docx renderer parses them back
into real Word tables. Both sides need the same rules for escaping, splitting,
grouping lines into table blocks and deciding which row is the delimiter rule,
so they live here rather than being duplicated (and drifting) in two places.

Every consumer goes through these helpers: :func:`iter_segments` is what the
.docx renderer walks the memo with, and :func:`content_rows` is what the test
suite and ``scripts/smoke_installed_wheel.py`` count rows with.
"""
from typing import Iterator, List, Optional, Sequence, Tuple

from creditmemo.text import strip_emphasis

__all__ = [
    "escape_cell",
    "unescape_cell",
    "split_row",
    "is_table_line",
    "has_separator_shape",
    "separator_index",
    "iter_segments",
    "iter_table_blocks",
    "block_to_rows",
    "content_rows",
]


def escape_cell(value) -> str:
    """
    Make an arbitrary value safe to interpolate into a Markdown table cell.

    A raw ``|`` in borrower text, a risk description or a use-of-proceeds
    string would otherwise open a new cell and silently shift every value to
    its right into the wrong column. Backslashes are escaped first so that a
    literal ``\\`` before a pipe cannot swallow the pipe's escape.

    Newlines are folded to spaces: a Markdown table row is a single line, so an
    embedded newline would truncate the row.
    """
    text = "" if value is None else str(value)
    text = text.replace("\\", "\\\\").replace("|", "\\|")
    return text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")


def unescape_cell(text: str) -> str:
    """Inverse of :func:`escape_cell` for a single already-split cell."""
    out: List[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text):
            out.append(text[i + 1])
            i += 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def split_row(line: str) -> List[str]:
    """
    Split one Markdown table row into its cell texts.

    Splits on unescaped ``|`` only, drops the leading/trailing delimiters, and
    unescapes each cell. Emphasis markers are stripped through
    :func:`creditmemo.text.strip_emphasis` — the same function the .docx
    paragraph path uses, so a table cell and a paragraph of the same document
    cannot disagree about whether a character is syntax or content. They did:
    this side stripped only ``**`` while the paragraph side stripped every
    ``*``, so a lone asterisk survived here and was deleted there.
    """
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    # Drop a single trailing delimiter, but only if it is not escaped.
    if stripped.endswith("|") and not stripped.endswith("\\|"):
        stripped = stripped[:-1]

    cells: List[str] = []
    buf: List[str] = []
    i = 0
    while i < len(stripped):
        ch = stripped[i]
        if ch == "\\" and i + 1 < len(stripped):
            buf.append(ch)
            buf.append(stripped[i + 1])
            i += 2
            continue
        if ch == "|":
            cells.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    cells.append("".join(buf))

    return [strip_emphasis(unescape_cell(c)).strip() for c in cells]


def is_table_line(line: str) -> bool:
    """True if this line is part of a Markdown pipe table."""
    return line.strip().startswith("|")


def has_separator_shape(line: str) -> bool:
    """
    True if ``line`` looks like a GFM delimiter rule: every cell non-empty and
    made only of ``-`` and ``:``.

    Shape alone must never decide whether a row is dropped. ``| - | - | - |`` is
    an ordinary content row — ``-`` is the commonest not-applicable placeholder
    an underwriter types — and it has exactly this shape. Only
    :func:`separator_index` decides, and it decides by position, because
    position is what the renderers actually control: each emits exactly one
    delimiter rule, immediately under the header.

    The non-empty requirement is GFM's rule for a valid delimiter row. It is not
    what keeps a signature-block row such as ``| IC Chair | | | |`` out of the
    rule: that row is content because of the words in it and because it sits at
    index 2 of its block, not because its other cells are empty. What the
    requirement does exclude is a block whose second line is ``| | | |`` — an
    all-empty row is not a valid delimiter, so that block has no delimiter and
    every line in it is content.
    """
    cells = split_row(line)
    if not cells:
        return False
    return all(c and set(c) <= set("-:") for c in cells)


def separator_index(block: Sequence[str]) -> Optional[int]:
    """
    Index of ``block``'s delimiter rule, or ``None`` if the block has none.

    GFM puts the delimiter immediately under the header row, and that is where
    both renderers emit it, so index 1 is the only candidate. Every other line
    is memo content whatever characters it happens to be made of.
    """
    if len(block) > 1 and has_separator_shape(block[1]):
        return 1
    return None


def iter_segments(lines: Sequence[str]) -> Iterator[Tuple[str, object]]:
    """
    Walk ``lines`` in document order, yielding ``("table", block)`` for each
    contiguous run of table lines and ``("text", line)`` for everything else.

    Blank lines and any non-table line end a block, so two tables separated by
    a heading are two blocks. The .docx renderer drives its whole output from
    this, and the conservation gates count rows from it, so the two sides cannot
    disagree about where one table stops and the next begins.

    A run of pipe lines is a table only if it carries a delimiter rule where GFM
    requires one — immediately under the header. A leading ``|`` alone is not
    enough, and treating it as enough silently turned underwriter prose into a
    Word table: ``deal_summary="| we structured this as a leveraged loan"``
    left the Markdown as written and arrived in the .docx as a one-cell table,
    with the pipe eaten. Every table this package emits has its rule at index 1,
    so no memo table is affected; a lone pipe line is now what it reads as,
    which is a sentence.
    """
    block: List[str] = []

    def flush(block):
        if separator_index(block) is not None:
            yield "table", block
        else:
            for stray in block:
                yield "text", stray

    for line in lines:
        if is_table_line(line):
            block.append(line)
            continue
        if block:
            for item in flush(block):
                yield item
            block = []
        yield "text", line
    if block:
        for item in flush(block):
            yield item


def iter_table_blocks(lines: Sequence[str]) -> Iterator[List[str]]:
    """Yield just the table blocks of :func:`iter_segments`, in order."""
    for kind, payload in iter_segments(lines):
        if kind == "table":
            yield payload  # type: ignore[misc]


def block_to_rows(block: Sequence[str]) -> List[List[str]]:
    """
    Turn a table block into content rows, dropping its delimiter rule.

    Exactly one line can be dropped — the one :func:`separator_index` points at.
    Nothing is dropped for looking like a rule, so a risk row of ``| - | - | - |``
    reaches the Word document like any other.

    Every row is padded to the widest row in the block so no cell is lost when
    a row is ragged; ragged input should not happen for memos built through
    :func:`escape_cell`, but dropping underwriter text is never the right
    failure mode.
    """
    sep = separator_index(block)
    rows = [split_row(line) for i, line in enumerate(block) if i != sep]
    if not rows:
        return []
    width = max(len(r) for r in rows)
    return [r + [""] * (width - len(r)) for r in rows]


def content_rows(lines: Sequence[str]) -> List[List[str]]:
    """
    Every memo table row in ``lines``, in document order, delimiter rules removed.

    This is the one definition of what counts as a row. The .docx gates and
    ``scripts/smoke_installed_wheel.py`` both call it, so neither can drift into
    its own idea of what a separator is — a second, subtly different definition
    is how an all-dash row went missing from the Word file and from the expected
    count at the same time, leaving the conservation check green.
    """
    return [row for block in iter_table_blocks(lines) for row in block_to_rows(block)]
