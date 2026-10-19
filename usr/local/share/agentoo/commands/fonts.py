#!/usr/bin/env python3
"""Installed-font diagnostics, Kitty selection, and read-only browser previews."""
import argparse
import contextlib
import io
import fcntl
import html
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import termios
import tty
import unicodedata

DATA = Path(__file__).resolve().parent.parent / 'fonts'
ROLES = ('monospace', 'sans-serif', 'serif', 'emoji')

def run(*args, **kw):
    return subprocess.run([str(x) for x in args], check=True, **kw)

def output(*args):
    return run(*args, capture_output=True, text=True).stdout.strip()

def read(path):
    return path.read_text() if path.exists() else ''

def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError(f'refusing to replace symlink: {path}')
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.agentoo-fonts-')
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(text)
        if path.exists():
            os.chmod(name, path.stat().st_mode & 0o777)
        else:
            os.chmod(name, 0o644)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)

def config_home():
    return Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config')))

def shell(*args):
    return shlex.join([str(x) for x in args])

def undo(*args):
    print('To revert: ' + shell('agentoo', 'fonts', *args))

def samples(suite):
    data = json.loads((DATA / 'samples.json').read_text())
    if suite == 'width':
        return {'width': [f'{shutil.get_terminal_size().columns} columns × {shutil.get_terminal_size().lines} rows',
                          ''.join(str((i+1)//10 % 10) if (i+1)%10 == 0 else str((i+1)%10) for i in range(shutil.get_terminal_size().columns)),
                          '|1234567890|abcdefghij|αβγδεζηθικ|中文中文中文中文中文|']}
    return data if suite == 'all' else {suite: data[suite]}

def terminal_test(a):
    print('Visual inspection only: printing does not establish glyph coverage.')
    for name, rows in samples(a.suite).items():
        print('\n' + name.upper())
        for row in rows:
            print(row)
        if name == 'smoke' and not a.plain and sys.stdout.isatty():
            print('\x1b[1mBold\x1b[0m / \x1b[3mItalic\x1b[0m / \x1b[1;3mBold Italic\x1b[0m / \x1b[4mUnderline\x1b[0m / \x1b[4:3mUndercurl\x1b[0m')
        if getattr(a, 'codepoints', False):
            chars = sorted(set(''.join(rows)) - set(' '), key=ord)
            columns = min(a.columns, 6)
            for i in range(0, len(chars), columns):
                group = chars[i:i+columns]
                print(' '.join(f'{c} U+{ord(c):04X}' for c in group))

def browser_test(a, font=None):
    rows = samples(a.suite)
    families = output('fc-list', '--format=%{family[0]}\n').splitlines()
    options = ''.join(f'<option>{html.escape(f)}</option>' for f in sorted(set(families)))
    # Private-use icons require an explicitly named family in Firefox.
    nerd_fallback = next((family for family in ('Symbols Nerd Font Mono', 'Symbols Nerd Font')
                          if family in families), '') if font is None else ''
    if nerd_fallback:
        selection_note = f'The right side starts with {html.escape(nerd_fallback)} after the generic font.'
    elif font is not None:
        selection_note = 'The right side starts with your requested candidate font.'
    else:
        selection_note = 'No supported Symbols Nerd Font was found; both sides start with the generic font.'
    sections = ''
    for name, lines in rows.items():
        content = 'Latin reference: ABC abc 0123 café\n' + '\n'.join(lines)
        codes = ' '.join(f'U+{ord(c):04X}' for c in sorted(set(content)-{'\n', ' '}, key=ord))
        sections += f'<section><h2>{html.escape(name)}</h2><div class="pair"><pre>{html.escape(content)}</pre><pre class="candidate">{html.escape(content)}</pre></div><details><summary>Codepoints</summary>{codes}</details></section>'
    page = '''<!doctype html><meta charset="utf-8"><title>Agentoo font preview</title>
<style>body{margin:2rem;font:16px system-ui;background:#f5f4ef;color:#222}label{margin-right:1rem}section{border-top:1px solid #aaa;margin-top:2rem}.pair{display:grid;grid-template-columns:1fr 1fr;gap:2rem;overflow:auto}pre{font:20px monospace;line-height:1.7;white-space:pre-wrap}details{overflow-wrap:anywhere}header{position:sticky;top:0;background:#f5f4ef;padding:1rem 0}select,input{font:inherit;max-width:24rem}</style>
<header><h1>Agentoo font preview</h1><label>Candidate <input id="font" list="fonts"></label><datalist id="fonts">OPTIONS</datalist><label>Size <input id="size" type="number" value="20" min="6" max="96"></label><label>Role <select id="role"><option>monospace</option><option>sans-serif</option><option>serif</option></select></label><label><input id="fallback" type="checkbox">Fallback after current default</label><p>Left: current generic font. Right: candidate stack. Latin reference: ABC abc 0123 café.</p><p>Nerd icons use private-use codepoints: explicitly name a compatible Nerd font. SELECTION_NOTE The left remains generic only. Successful rendering on the right does not enable Nerd icons elsewhere in Firefox.</p><p>Preview only; no Firefox preferences are changed. Use Firefox Inspector → Fonts to inspect actual rendered fonts.</p></header>SECTIONS
<script>const f=document.querySelector('#font'),s=document.querySelector('#size'),r=document.querySelector('#role'),b=document.querySelector('#fallback');f.value=INITIAL;b.checked=FALLBACK;function update(){let quoted='"'+f.value.replaceAll('\\\\','\\\\\\\\').replaceAll('"','\\\\"')+'"';let stack=f.value?(b.checked?r.value+', '+quoted:quoted+', '+r.value):r.value;document.querySelectorAll('pre').forEach(p=>{p.style.fontSize=s.value+'px';p.style.fontFamily=p.classList.contains('candidate')?stack:r.value});}for(let e of [f,s,r,b])e.addEventListener('input',update);update();</script>'''
    page = page.replace('OPTIONS', options).replace('SECTIONS', sections).replace('INITIAL', json.dumps(font or nerd_fallback).replace('<', '\\u003c'))
    page = page.replace('FALLBACK', json.dumps(bool(nerd_fallback))).replace('SELECTION_NOTE', selection_note)
    path = Path(a.output).expanduser().absolute() if a.output else Path(os.environ.get('XDG_CACHE_HOME', str(Path.home()/'.cache'))) / 'agentoo/fonts/preview.html'
    write(path, page)
    print(path)
    if not a.no_open:
        launcher = next((executable for name in ('firefox', 'firefox-bin')
                         if (executable := shutil.which(name))), None)
        if launcher is None:
            raise ValueError('Firefox launcher not found (tried firefox and firefox-bin); '
                             f'open {path} manually, or use --no-open to generate only')
        run(launcher, path.as_uri())


def fontconfig_rules():
    """Read Gentoo's enabled rule selections without modifying symlinks."""
    if shutil.which('eselect'):
        try:
            report = output('eselect', 'fontconfig', 'list')
            names = re.findall(r'^\s*\[\d+\]\s+(\S+)\s+\*\s*$', report, re.M)
            return names, 'eselect fontconfig list'
        except (OSError, subprocess.CalledProcessError):
            pass
    directory = Path('/etc/fonts/conf.d')
    return sorted(p.name for p in directory.glob('*.conf')), '/etc/fonts/conf.d (eselect unavailable or failed)'


def fontconfig_warnings(names):
    enabled = set(names)
    groups = {
        'hinting levels': ['10-hinting-full.conf', '10-hinting-medium.conf', '10-hinting-none.conf', '10-hinting-slight.conf'],
        'subpixel orders': ['10-sub-pixel-'+x+'.conf' for x in ('none','rgb','bgr','vrgb','vbgr')],
        'antialias switches': ['10-no-antialias.conf', '10-yes-antialias.conf'],
        'bitmap policies': ['70-no-bitmaps.conf', '70-no-bitmaps-and-emoji.conf', '70-no-bitmaps-except-emoji.conf', '70-yes-bitmaps.conf'],
        'LCD filters': ['11-lcdfilter-'+x+'.conf' for x in ('default','legacy','light','none')],
    }
    warnings = []
    for label, alternatives in groups.items():
        found = sorted(enabled.intersection(alternatives))
        if len(found) > 1:
            warnings.append(f'Potentially conflicting {label}: '+', '.join(found))
    if '10-unhinted.conf' in enabled and enabled.intersection({'10-hinting-full.conf','10-hinting-medium.conf','10-hinting-slight.conf','10-autohint.conf'}):
        warnings.append('Unhinted rendering is enabled alongside hinting rules; inspect effective matches.')
    return warnings


def kitty_paths():
    base = config_home() / 'kitty'
    return base / 'kitty.conf', base / 'agentoo-fonts.conf'


def kitty_settings(extra=None):
    env = os.environ.copy()
    env.pop('AGENTOO_KITTY_EXTRA', None)
    if extra:
        env['AGENTOO_KITTY_EXTRA'] = str(extra)
    code = 'import runpy; runpy.run_path(' + repr(str(DATA / 'kitty-settings.py')) + ')'
    return json.loads(run('kitty', '+runpy', code, env=env, capture_output=True, text=True).stdout)


def validate_font(family, style=None):
    if not family or any(c in family for c in '\r\n\0'):
        raise ValueError('font must be a nonempty single-line family name')
    faces = output('fc-list', '--format=%{family}\t%{style}\n').splitlines()
    matching = [line.split('\t', 1) for line in faces
                if family.casefold() in [n.strip().casefold() for n in line.split('\t')[0].split(',')]]
    if not matching:
        raise ValueError(f'font family is not installed: {family}; use agentoo fonts list')
    if style and not any(style.casefold() in [s.strip().casefold() for s in row[1].split(',')]
                         for row in matching if len(row) == 2):
        raise ValueError(f'style is not installed: {family} / {style}')
    # Ask Kitty as well: fontconfig presence alone does not mean Kitty can select it.
    with tempfile.TemporaryDirectory(prefix='agentoo-font-check-') as directory:
        path = Path(directory) / 'selection.conf'
        write(path, selection_text('', family, style))
        chosen = kitty_settings(path)['faces']['medium']
    if chosen['family'].casefold() != family.casefold():
        raise ValueError(f'Kitty substituted {chosen["family"]!r} for {family!r}')


def selection_text(original, family=None, style=None, size=None, geometry=None):
    keys = {'font_family', 'bold_font', 'italic_font', 'bold_italic_font'} if family else set()
    if size is not None:
        keys.add('font_size')
    geometry = geometry or {}
    lines = []
    for line in original.splitlines():
        parts = line.split()
        if parts and (parts[0] in keys or
                      (parts[0] == 'modify_font' and len(parts) > 1 and parts[1] in geometry)):
            continue
        lines.append(line)
    if family:
        spec = 'family=' + shlex.quote(family)
        if style:
            spec += ' style=' + shlex.quote(style)
        lines += ['font_family ' + spec, 'bold_font auto', 'italic_font auto', 'bold_italic_font auto']
    if size is not None:
        lines.append('font_size ' + str(size))
    lines += [f'modify_font {key} {value}' for key, value in geometry.items()]
    return '\n'.join(lines).rstrip() + '\n' if lines else ''


def reload_kitties():
    """USR1 is Kitty's native reload mechanism; never signal another user's process."""
    count = 0
    failures = []
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            if proc.stat().st_uid != os.getuid() or (proc / 'comm').read_text().strip() != 'kitty':
                continue
            argv = (proc / 'cmdline').read_bytes().split(b'\0')
            if len(argv) > 1 and argv[1].startswith(b'+'):
                continue  # Kitty's Python/kitten helpers are not GUI instances.
            os.kill(int(proc.name), signal.SIGUSR1)
            count += 1
        except ProcessLookupError:
            pass
        except PermissionError:
            failures.append(proc.name)
        except FileNotFoundError:
            pass
    print(f'Requested configuration reload in {count} Kitty processes owned by this user.')
    if failures:
        print('Could not signal Kitty PIDs: ' + ', '.join(failures))
    print('Instances using custom config paths or launch overrides may retain their own settings.')


def save_selection(text, expected=None):
    config, fragment = kitty_paths()
    previous = read(fragment)
    if expected is not None and previous != expected:
        raise ValueError('font fragment changed during preview; no changes saved. Reopen the preview.')
    before = read(config)
    include = 'include agentoo-fonts.conf'
    # Validate both destinations before writing either.
    if fragment.is_symlink() or config.is_symlink():
        raise ValueError('refusing to replace a symlinked Kitty configuration')
    existed = fragment.exists()
    write(fragment, text)
    try:
        if include not in [line.strip() for line in before.splitlines()]:
            write(config, before.rstrip() + '\n\n# Font selections made by agentoo fonts\n' + include + '\n')
    except OSError:
        if existed:
            write(fragment, previous)
        else:
            fragment.unlink(missing_ok=True)
        raise
    print(f'Updated {fragment}')
    undo('kitty-config', '--value', previous)
    reload_kitties()


def preview(a, chooser=False, trace=None):
    if a.font:
        validate_font(a.font, a.style)
    original = read(kitty_paths()[1])
    with tempfile.TemporaryDirectory(prefix='agentoo-font-preview-') as directory:
        directory = Path(directory)
        candidate, accepted = directory / 'fonts.conf', directory / 'accepted.conf'
        write(candidate, selection_text(original, a.font, a.style, a.size))
        socket = 'unix:' + str(directory / 'kitty.sock')
        state = {'candidate': str(candidate), 'accepted': str(accepted), 'socket': socket,
                 'chooser': chooser, 'suite': a.suite, 'text': getattr(a, 'text', None),
                 'read_only': bool(trace)}
        state_path = directory / 'state.json'
        write(state_path, json.dumps(state))
        cmd = ['kitty', '--class', 'agentoo-font-preview', '--listen-on', socket]
        if trace:
            cmd.append('--debug-font-fallback')
        # Keep normal system/user config, then append the temporary selection.
        for path in kitty_settings()['paths'] + [str(candidate)]:
            cmd += ['--config', path]
        cmd += ['-o', 'allow_remote_control=socket-only', sys.executable,
                str(Path(__file__).resolve()), '_preview', str(state_path)]
        env = os.environ.copy()
        for key in ('TMUX', 'TMUX_PANE'):
            env.pop(key, None)
        if trace:
            with Path(trace).open('w') as log:
                run(*cmd, stderr=log, env=env)
            print('Kitty rendering trace:', trace)
        else:
            run(*cmd, env=env)
        if accepted.exists():
            save_selection(read(accepted), expected=original)
        else:
            print('Preview closed without saving.')


def adjust_geometry(value, direction):
    match = re.fullmatch(r'(-?\d+(?:\.\d+)?)(px|%)?', value)
    if not match:
        raise ValueError(f'unsupported cell adjustment: {value}')
    number, unit = float(match[1]), match[2] or ''
    number += direction
    number = max(50, min(200, number)) if unit == '%' else max(-20, min(40, number))
    return f'{number:g}{unit}'


def preview_child(state_path):
    state = json.loads(Path(state_path).read_text())
    candidate = Path(state['candidate'])
    if state['chooser']:
        run('kitten', 'choose-fonts', '--config-file-name', candidate, '--reload-in', 'none')
    initial = read(candidate)
    snapshot = kitty_settings(candidate)
    if snapshot['errors']:
        raise ValueError('invalid Kitty configuration: ' + '; '.join(snapshot['errors']))
    size = initial_size = float(snapshot['settings']['font_size'])
    geometry = dict(snapshot['geometry'])
    initial_geometry = dict(geometry)
    changed_geometry = {}
    paths = snapshot['paths']

    def reload_preview():
        write(candidate, selection_text(initial, size=size if size != initial_size else None,
                                        geometry=changed_geometry))
        run('kitten', '@', '--to', state['socket'], 'load-config', '--ignore-overrides',
            *paths, '-o', 'allow_remote_control=socket-only', capture_output=True, text=True)

    reload_preview()
    fd = sys.stdin.fileno()
    saved_tty = termios.tcgetattr(fd)
    try:
        # cbreak preserves normal newline processing for the sample sheet.
        tty.setcbreak(fd)
        while True:
            print('\x1b[2J\x1b[H', end='')
            print('AGENTOO KITTY DIAGNOSTIC' if state['read_only'] else
                  'AGENTOO KITTY PREVIEW — temporary until Save')
            print('Family:', snapshot['settings']['font_family'])
            print(f'Size: {size:g} pt | cell width: {geometry["cell_width"]} | cell height: {geometry["cell_height"]}')
            try:
                rows, cols, xpixels, ypixels = struct.unpack('HHHH', fcntl.ioctl(fd, termios.TIOCGWINSZ, b'\0' * 8))
                if cols and rows and xpixels and ypixels:
                    print(f'Grid: {cols} × {rows}; cell: {xpixels / cols:.1f} × {ypixels / rows:.1f} px')
            except OSError:
                pass
            print('+/- size | h/l narrower/wider | j/k shorter/taller | r reset')
            print('Cell adjustments retain their original unit (%, px, or points). Scroll for samples.')
            print('Ruler: ' + ''.join(str((i + 1) % 10) for i in range(80)))
            if state['text'] is not None:
                print('\nPROBLEM TEXT\n' + state['text'])
            terminal_test(argparse.Namespace(suite=state['suite'], plain=False, codepoints=False))
            print(f'\nSize {size:g} pt | width {geometry["cell_width"]} | height {geometry["cell_height"]}')
            print('+/- size | h/l width | j/k height | r reset | ' +
                  ('q/Esc close (diagnostic only)' if state['read_only'] else 's save | q/Esc cancel'))
            sys.stdout.flush()
            key = sys.stdin.read(1)
            if key in ('q', '\x1b', ''):
                return
            if key == 's' and not state['read_only']:
                write(Path(state['accepted']), read(candidate))
                return
            if key in ('+', '='):
                size = min(96, size + 0.5)
            elif key == '-':
                size = max(4, size - 0.5)
            elif key in 'hljk':
                name = 'cell_width' if key in 'hl' else 'cell_height'
                geometry[name] = adjust_geometry(geometry[name], 1 if key in 'lk' else -1)
                changed_geometry[name] = geometry[name]
            elif key == 'r':
                size, geometry = initial_size, dict(initial_geometry)
                changed_geometry = {}
            else:
                continue
            reload_preview()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved_tty)


def query(*args):
    """Diagnostics keep useful evidence when an optional tool fails."""
    try:
        return output(*args)
    except (OSError, subprocess.CalledProcessError) as error:
        return {'error': str(error)}


def installed_faces():
    records = output('fc-list', '--format=%{family}\t%{style}\t%{file}\t%{charset}\n')
    faces = []
    for row in records.splitlines():
        fields = row.split('\t')
        if len(fields) != 4:
            continue
        ranges = []
        for value in fields[3].split():
            bounds = value.split('-')
            ranges.append((int(bounds[0], 16), int(bounds[-1], 16)))
        faces.append({'family': fields[0], 'style': fields[1], 'file': fields[2], 'ranges': ranges})
    return faces


def problem_characters(text, faces, pattern='monospace'):
    result = []
    for char in sorted(set(text) - set(' \n'), key=ord):
        covers = sorted({face['family'] for face in faces
                         if any(lo <= ord(char) <= hi for lo, hi in face['ranges'])})
        result.append({'character': char, 'codepoint': f'U+{ord(char):04X}',
                       'name': unicodedata.name(char, 'unnamed'),
                       'category': unicodedata.category(char), 'combining': unicodedata.combining(char),
                       'covering_families': covers,
                       'fontconfig_match': query('fc-match', '--format=%{family}\t%{file}',
                                                f'{pattern}:charset={ord(char):x}')})
    return result


def doctor_report(a):
    names, source = fontconfig_rules()
    faces = installed_faces()
    report = {
        'scope': 'Installed coverage and resolved default configuration; not live application state.',
        'environment': {key: os.environ.get(key) for key in
                        ('TERM', 'TMUX', 'SSH_CONNECTION', 'FONTCONFIG_FILE', 'FONTCONFIG_PATH', 'XDG_CONFIG_HOME')},
        'tools': {name: shutil.which(name) for name in ('fc-list', 'fc-match', 'fc-conflist', 'fc-cache', 'eselect', 'kitty', 'kitten')},
        'rules': {'source': source, 'enabled': names, 'warnings': fontconfig_warnings(names),
                  'loaded': query('fc-conflist')},
        'matches': {family: query('fc-match', '-v', family) for family in ROLES},
        'faces': faces,
        'coverage': {},
        'font_directories': sorted({str(Path(face['file']).parent) for face in faces}),
        'packages': {},
        'kitty': {},
        'notes': ['Fontconfig matches are candidates, not proof of rendered fonts.',
                  'Kitty can draw some terminal symbols itself; font coverage is not the whole renderer.',
                  'Combining marks and emoji sequences require visual inspection.',
                  'Restart applications after installing fonts if they retain an old font list.',
                  'Use doctor --render for a fresh Kitty fallback trace; browser preview is a different renderer.'],
    }
    for group, rows in samples(a.suite).items():
        chars = set(''.join(rows)) - set(' \n')
        missing = [f'U+{ord(char):04X}' for char in sorted(chars, key=ord)
                   if not any(lo <= ord(char) <= hi for face in faces for lo, hi in face['ranges'])]
        report['coverage'][group] = {'total': len(chars), 'covered': len(chars) - len(missing), 'missing': missing}
    for package in sorted(Path('/var/db/pkg/media-fonts').glob('*')):
        report['packages'][package.name] = {'USE': read(package / 'USE').strip(),
                                          'repository': read(package / 'repository').strip()}
    # Package ownership is exact, including fonts installed outside media-fonts.
    font_files = {face['file'] for face in faces}
    owners = {}
    for contents in Path('/var/db/pkg').glob('*/*/CONTENTS'):
        for line in read(contents).splitlines():
            fields = line.split()
            if len(fields) > 1 and fields[0] == 'obj' and fields[1] in font_files:
                owners[fields[1]] = str(contents.parent.relative_to('/var/db/pkg'))
    for face in faces:
        face['package'] = owners.get(face['file'], '(not Portage-owned)')
    if a.text is not None:
        report['text'] = {'input': a.text, 'NFC': unicodedata.normalize('NFC', a.text),
                          'NFD': unicodedata.normalize('NFD', a.text),
                          'characters': problem_characters(a.text, faces)}
    if shutil.which('kitty'):
        try:
            report['kitty'] = kitty_settings()
            report['kitty']['fragment'] = read(kitty_paths()[1])
            report['kitty']['version'] = query('kitty', '--version')
        except (OSError, ValueError, subprocess.CalledProcessError) as error:
            report['kitty'] = {'error': str(error)}
    return report


def print_doctor(report):
    print(report['scope'])
    print('\nTools:', json.dumps(report['tools'], ensure_ascii=False))
    print('\nEnvironment:', json.dumps(report['environment'], ensure_ascii=False))
    print('\nInstalled font packages:')
    for package, info in report['packages'].items():
        print(f'  {package}::{info["repository"]} USE="{info["USE"]}"')
    print('\nFont directories:', ', '.join(report['font_directories']))
    print('\nVisible faces:')
    for face in report['faces']:
        print(f'  {face["family"]} [{face["style"]}] — {face["file"]} ({face["package"]})')
    print('\nFontconfig rules:', ', '.join(report['rules']['enabled']))
    print('Loaded rules:\n', report['rules']['loaded'])
    for warning in report['rules']['warnings']:
        print('NOTE:', warning)
    print('\nEffective fontconfig matches and rendering properties:')
    for family, match in report['matches'].items():
        print(f'\n{family}:\n{match}')
    print('\nSample codepoint coverage across installed fonts:')
    for suite, coverage in report['coverage'].items():
        print(f'  {suite}: {coverage["covered"]}/{coverage["total"]}; missing: {", ".join(coverage["missing"]) or "none"}')
    print('\nKitty default configuration (includes resolved; launch overrides not observed):')
    print(json.dumps(report['kitty'], ensure_ascii=False, indent=2))
    if 'text' in report:
        print('\nProblem text:', json.dumps(report['text'], ensure_ascii=False, indent=2))
    for note in report['notes']:
        print('NOTE:', note)


def main():
    parser = argparse.ArgumentParser(prog='agentoo fonts', description=__doc__,
        epilog='Install/remove fonts with Portage. With no command, show Kitty configuration.')
    sub = parser.add_subparsers(dest='command')
    suites = (*json.loads((DATA / 'samples.json').read_text()), 'width', 'all')
    sub.add_parser('status', help='Show resolved default Kitty font settings')
    p = sub.add_parser('list', help='List installed families and styles')
    p.add_argument('filter', nargs='?', default='')
    p.add_argument('--nerd', action='store_true')
    for name in ('test', 'preview', 'set'):
        p = sub.add_parser(name, help={'test': 'Print visual samples', 'preview': 'Try fonts in a dedicated window',
                                      'set': 'Choose interactively, or apply an explicit Kitty selection'}[name])
        if name == 'test':
            p.add_argument('suite', choices=suites, nargs='?', default='all')
        else:
            p.add_argument('font', nargs='?')
            p.add_argument('--size', type=float)
            p.add_argument('--style')
            p.add_argument('--suite', choices=suites, default='all')
        if name != 'set':
            p.add_argument('--target', choices=('kitty', 'firefox'), default='kitty')
            p.add_argument('--output', help='Browser HTML output path')
            p.add_argument('--no-open', action='store_true', help='Only generate browser HTML')
            p.add_argument('--plain', action='store_true')
            p.add_argument('--codepoints', action='store_true')
            p.add_argument('--columns', type=int, choices=range(1, 7), default=6)
    p = sub.add_parser('doctor', help='Report font inventory, policy, matching, and Kitty configuration')
    p.add_argument('--suite', choices=suites, default='all')
    p.add_argument('--text')
    p.add_argument('--json', action='store_true')
    p.add_argument('--render', action='store_true', help='Open a fresh Kitty sample window and capture fallback tracing')
    p.add_argument('--output', help='Rendering trace file (requires --render)')
    p = sub.add_parser('coverage', help='Check sample coverage in one matched face')
    p.add_argument('font')
    p.add_argument('--suite', choices=suites, default='all')
    p = sub.add_parser('explain', help='Explain codepoints and fontconfig candidates')
    p.add_argument('text')
    p.add_argument('--font', default='monospace')
    p = sub.add_parser('kitty-config', help='Restore a fragment from a printed revert command')
    p.add_argument('--value', required=True)
    a = parser.parse_args()
    if getattr(a, 'size', None) is not None and not 4 <= a.size <= 96:
        parser.error('--size must be between 4 and 96 points')
    if getattr(a, 'style', None) and not a.font:
        parser.error('--style requires a font')
    if getattr(a, 'target', 'kitty') != 'firefox' and (getattr(a, 'no_open', False) or
            (a.command in ('test', 'preview') and a.output)):
        parser.error('--no-open and --output require --target firefox')
    if a.command in (None, 'status'):
        print(json.dumps(kitty_settings(), ensure_ascii=False, indent=2))
        print('Launch overrides and runtime selections may differ. Use doctor for the full environment.')
    elif a.command == 'list':
        for line in sorted(set(output('fc-list', '--format=%{family}\t%{style}\n').splitlines())):
            if a.filter.casefold() in line.casefold() and (not a.nerd or 'nerd' in line.casefold()):
                print(line)
    elif a.command == 'test':
        browser_test(a) if a.target == 'firefox' else terminal_test(a)
    elif a.command == 'preview':
        if a.target == 'firefox':
            if a.size is not None or a.style:
                parser.error('browser preview uses its page controls for size; --size/--style are Kitty options')
            browser_test(a, a.font)
        else:
            preview(a)
    elif a.command == 'set':
        if a.font:
            validate_font(a.font, a.style)
            save_selection(selection_text(read(kitty_paths()[1]), a.font, a.style, a.size))
        else:
            preview(a, chooser=True)
    elif a.command == 'kitty-config':
        save_selection(a.value)
    elif a.command == 'doctor':
        if a.output and not a.render:
            parser.error('--output requires --render')
        report = doctor_report(a)
        if a.render:
            trace = Path(a.output).expanduser().absolute() if a.output else None
            # Do not overwrite a predictable or symlinked file in a shared directory.
            if not a.output:
                fd, name = tempfile.mkstemp(prefix='agentoo-font-trace-', suffix='.log')
                os.close(fd)
                trace = Path(name)
            # Keep --json stdout machine-readable even when rendering is requested.
            with contextlib.redirect_stdout(io.StringIO()) as messages:
                preview(argparse.Namespace(font=None, style=None, size=None, suite=a.suite, text=a.text), trace=trace)
            if not a.json:
                print(messages.getvalue(), end='')
            report['render_trace'] = str(trace)
        print(json.dumps(report, ensure_ascii=False, indent=2)) if a.json else print_doctor(report)
    elif a.command == 'explain':
        print(json.dumps(problem_characters(a.text, installed_faces(), a.font), ensure_ascii=False, indent=2))
        print('Fontconfig candidates do not establish the rendered font.')
    elif a.command == 'coverage':
        record = output('fc-match', '--format=%{family}\n%{file}\n%{charset}', a.font).splitlines()
        covered = set()
        for part in record[2].split():
            bounds = part.split('-')
            covered.update(range(int(bounds[0], 16), int(bounds[-1], 16) + 1))
        chars = set(''.join(s for rows in samples(a.suite).values() for s in rows)) - set(' \n')
        missing = sorted((c for c in chars if ord(c) not in covered), key=ord)
        print('Matched face:', record[0], record[1])
        print(f'{len(chars) - len(missing)}/{len(chars)} distinct sample codepoints present.')
        for char in missing:
            print(f'Missing U+{ord(char):04X} {unicodedata.name(char, "unnamed")}')
        print('Fallback, composition, shaping, and appearance require visual inspection.')


if __name__ == '__main__':
    try:
        if len(sys.argv) == 3 and sys.argv[1] == '_preview':
            preview_child(sys.argv[2])
        else:
            main()
    except (ValueError, OSError, subprocess.CalledProcessError, KeyError) as error:
        print(f'agentoo fonts: {error}', file=sys.stderr)
        sys.exit(2)
    except KeyboardInterrupt:
        print('\nCancelled.', file=sys.stderr)
        sys.exit(130)
