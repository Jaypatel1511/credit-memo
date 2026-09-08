"""
Shared Markdown-table helpers.

The Markdown renderer emits pipe tables; the .docx renderer parses them back
into real Word tables. Both sides need the same rules for escaping, splitting
and recognising separator rows, so they live here rather than being duplicated
(and drifting) in two places.
"""
from typing import Iterator, List, Sequence

__all__ = [
    "escape_cell",
    "unescape_cell",
    "split_row",
    "is_table_line",
    "is_separator_row",
    "iter_table_blocks",
    "block_to_rows",
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
    unescapes each cell. Markdown bold markers are stripped so table cells read
    the same way the paragraph path renders them.
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

    return [unescape_cell(c).replace("**", "").strip() for c in cells]


def is_table_line(line: str) -> bool:
    """True if this line is part of a Markdown pipe table."""
    return line.strip().startswith("|")


def is_separator_row(line: str) -> bool:
    """
    True for the ``|---|---|`` rule under a table header.

    Every cell must be non-empty and made only of ``-`` and ``:``. A signature
    block row such as ``| IC Chair | | | |`` has empty cells and is therefore
    content, not a separator.
    """
    cells = split_row(line)
    if not cells:
        return False
    return all(c and set(c) <= set("-:") for c in cells)


def iter_table_blocks(lines: Sequence[str]) -> Iterator[List[str]]:
    """
    Yield each contiguous run of table lines from ``lines`` as a list of lines.

    Blank lines and any non-table line end a block, so two tables separated by
    a heading are two blocks.
    """
    block: List[str] = []
    for line in lines:
        if is_table_line(line):
            block.append(line)
        elif block:
            yield block
            block = []
    if block:
        yield block


def block_to_rows(block: Sequence[str]) -> List[List[str]]:
    """
    Turn a table block into content rows, dropping separator rows.

    Every row is padded to the widest row in the block so no cell is lost when
    a row is ragged; ragged input should not happen for memos built through
    :func:`escape_cell`, but dropping underwriter text is never the right
    failure mode.
    """
    rows = [split_row(line) for line in block if not is_separator_row(line)]
    if not rows:
        return []
    width = max(len(r) for r in rows)
    return [r + [""] * (width - len(r)) for r in rows]
