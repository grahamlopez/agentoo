"""Verify relative Markdown links and heading anchors across repository docs."""
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[5]
LINK_RE = re.compile(r'!?\[[^\]]*\]\(([^)\s]+)(?:\s+"[^"]*")?\)')
FENCE_RE = re.compile(r'^\s*(```|~~~)')
HEADING_RE = re.compile(r'^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$')
INLINE_CODE_RE = re.compile(r'`[^`]*`')


def tracked_markdown_files():
    if (ROOT / '.git').exists():
        result = subprocess.run(
            ['git', 'ls-files', '--', '*.md'],
            cwd=ROOT, text=True, capture_output=True, check=True,
        )
        return [ROOT / rel for rel in result.stdout.splitlines() if (ROOT / rel).is_file()]
    files = []
    for rel in ('README.md', 'AGENTS.md'):
        path = ROOT / rel
        if path.is_file():
            files.append(path)
    for directory in (ROOT / 'etc/agentoo', ROOT / 'usr/local/share/agentoo'):
        if directory.is_dir():
            files.extend(sorted(directory.rglob('*.md')))
    return files


def strip_fenced_blocks(text):
    out = []
    in_fence = False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            out.append('')
            continue
        out.append('' if in_fence else line)
    return out


def github_slug(heading):
    # Strip inline markdown formatting while preserving link text and code spans.
    plain = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', heading)
    plain = plain.replace('`', '')
    slug = plain.strip().lower()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = slug.replace(' ', '-')
    return slug


def heading_anchors(path):
    anchors = set()
    counts = {}
    for line in strip_fenced_blocks(path.read_text(encoding='utf-8')):
        match = HEADING_RE.match(line)
        if not match:
            continue
        base = github_slug(match.group(1))
        count = counts.get(base, 0)
        anchors.add(base if count == 0 else f'{base}-{count}')
        counts[base] = count + 1
    return anchors


class DocLinkTests(unittest.TestCase):
    def test_relative_markdown_links_resolve(self):
        md_files = tracked_markdown_files()
        self.assertTrue(md_files, 'expected repository Markdown files')
        anchors_cache = {}
        broken = []

        for source in md_files:
            rel_source = source.relative_to(ROOT)
            for lineno, line in enumerate(strip_fenced_blocks(source.read_text(encoding='utf-8')), 1):
                cleaned = INLINE_CODE_RE.sub('', line)
                for match in LINK_RE.finditer(cleaned):
                    raw_target = match.group(1)
                    if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', raw_target):
                        continue
                    path_part, _, fragment = raw_target.partition('#')
                    target = source if not path_part else (source.parent / path_part).resolve()
                    if not target.exists():
                        broken.append(f'{rel_source}:{lineno}: missing target {raw_target}')
                        continue
                    if fragment and target.is_file() and target.suffix == '.md':
                        if target not in anchors_cache:
                            anchors_cache[target] = heading_anchors(target)
                        if fragment not in anchors_cache[target]:
                            broken.append(f'{rel_source}:{lineno}: missing anchor #{fragment} in {target.relative_to(ROOT)}')

        self.assertEqual(broken, [], 'Broken Markdown links:\n' + '\n'.join(broken))

    def test_slug_and_code_stripping(self):
        self.assertEqual(github_slug('Native `gentoo-kernel` & NVIDIA'), 'native-gentoo-kernel--nvidia')
        lines = strip_fenced_blocks('ok [a](b.md)\n```md\n[bad](missing.md)\n```\nend\n')
        self.assertEqual(lines, ['ok [a](b.md)', '', '', '', 'end'])


if __name__ == '__main__':
    unittest.main()
