#!/usr/bin/env python3
"""Git commit-msg hook that wraps commit message body lines to a fixed width.

Preserves the subject line, blank lines, fenced/indented code blocks, quotes,
tables, Git comments/scissors, and trailers while wrapping prose paragraphs and
list items cleanly without breaking URLs or hyphenated tokens.
"""
import argparse
from pathlib import Path
import re
import sys
import textwrap

DEFAULT_WIDTH = 80
DEFAULT_SUBJECT_WIDTH = 80

SCISSORS_RE = re.compile(r'^# -+ >8 -+$')
EXEMPT_SUBJECT_RE = re.compile(r'^(?:Merge |Revert "|(?:fixup|squash|amend)! )')
FENCE_RE = re.compile(r'^\s*(```|~~~)')
LIST_RE = re.compile(r'^(\s*)([-*+]|\d+[.)])(\s+)(.*)$')
TRAILER_RE = re.compile(
    r'^(?:[A-Za-z]+-[A-Za-z0-9-]+|Fixes|Closes|Resolves|Refs|Cc|Link|Bug|Issue|Ticket):[ \t]+\S'
)


def _is_verbatim(line: str) -> bool:
    return (
        line.startswith('#')
        or line.startswith('>')
        or line.startswith('|')
        or line.startswith('    ')
        or line.startswith('\t')
        or bool(TRAILER_RE.match(line))
    )


def _wrap_block(text: str, width: int, initial_indent: str = '', subsequent_indent: str = '') -> str:
    return textwrap.fill(
        text,
        width=width,
        initial_indent=initial_indent,
        subsequent_indent=subsequent_indent,
        break_long_words=False,
        break_on_hyphens=False,
    )


def wrap_commit_message(message: str, width: int = DEFAULT_WIDTH) -> str:
    if not message.strip():
        return message

    trailing_newline = message.endswith('\n')
    lines = message.splitlines()
    out: list[str] = [lines[0]]  # Never wrap the subject line.

    in_fence = False
    para: list[str] = []
    list_item: tuple[str, str, list[str]] | None = None  # (prefix, cont_indent, parts)

    def flush() -> None:
        nonlocal para, list_item
        if para:
            out.append(_wrap_block(' '.join(para), width))
            para = []
        if list_item is not None:
            prefix, cont_indent, parts = list_item
            out.append(_wrap_block(' '.join(parts), width, prefix, cont_indent))
            list_item = None

    for idx in range(1, len(lines)):
        line = lines[idx]

        if SCISSORS_RE.match(line):
            flush()
            out.extend(lines[idx:])
            break

        if in_fence:
            out.append(line)
            if FENCE_RE.match(line):
                in_fence = False
            continue

        if FENCE_RE.match(line):
            flush()
            in_fence = True
            out.append(line)
            continue

        if not line.strip():
            flush()
            out.append('')
            continue

        match = LIST_RE.match(line)
        if match:
            flush()
            indent, marker, space, content = match.groups()
            prefix = f'{indent}{marker}{space}'
            list_item = (prefix, ' ' * len(prefix), [content.strip()])
            continue

        if (
            list_item is not None
            and line.startswith(' ')
            and not line.lstrip().startswith(('#', '>', '|'))
            and not TRAILER_RE.match(line.lstrip())
        ):
            list_item[2].append(line.strip())
            continue

        if _is_verbatim(line):
            flush()
            out.append(line)
            continue

        if list_item is not None:
            flush()
        para.append(line.strip())

    flush()
    result = '\n'.join(out)
    if trailing_newline:
        result += '\n'
    return result


def subject_error(message: str, max_width: int = DEFAULT_SUBJECT_WIDTH) -> str | None:
    if max_width <= 0:
        return None
    for line in message.splitlines():
        if SCISSORS_RE.match(line):
            return None
        if not line.strip() or line.startswith('#'):
            continue
        if EXEMPT_SUBJECT_RE.match(line):
            return None
        if len(line) > max_width:
            return (
                f'commit-msg: subject line is {len(line)} characters (max {max_width}).\n'
                'Shorten the subject line and move extra detail into the commit body.'
            )
        return None
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--width', type=int, default=DEFAULT_WIDTH,
                        help=f'Maximum line width for wrapped body lines (default: {DEFAULT_WIDTH})')
    parser.add_argument('--subject-width', type=int, default=DEFAULT_SUBJECT_WIDTH,
                        help=f'Maximum subject line length; 0 disables (default: {DEFAULT_SUBJECT_WIDTH})')
    parser.add_argument('message_file', type=Path, help='Path to the commit message file')
    args = parser.parse_args(argv)

    original = args.message_file.read_text(encoding='utf-8')
    error = subject_error(original, max_width=args.subject_width)
    if error is not None:
        print(error, file=sys.stderr)
        return 1

    wrapped = wrap_commit_message(original, width=args.width)
    if wrapped != original:
        args.message_file.write_text(wrapped, encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
