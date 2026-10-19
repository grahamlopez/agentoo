#!/usr/bin/env python3
"""Agentoo font diagnostics, installation and target configuration."""
import argparse
import configparser
import hashlib
import html
import io
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import termios
import tty
import unicodedata
import urllib.request
import zipfile

DATA = Path(__file__).resolve().parent.parent / 'fonts'
CATALOG = {'ubuntu-sans-mono': 'UbuntuSans', 'ubuntu-mono': 'UbuntuMono',
           'jetbrains-mono': 'JetBrainsMono', 'fira-code': 'FiraCode',
           'liberation-mono': 'LiberationMono', 'symbols': 'NerdFontsSymbolsOnly'}
PACKAGES = {'terminus': 'media-fonts/terminus-font', 'noto-cjk': 'media-fonts/noto-cjk',
            'noto-emoji': 'media-fonts/noto-emoji', 'unifont': 'media-fonts/unifont'}
ROLES = ('monospace', 'sans-serif', 'serif')

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

def target(a):
    if a.target != 'auto':
        return a.target
    # Visual tests can always print to the invoking terminal, including over SSH.
    # Configuration commands must identify a supported local target reliably.
    testing = getattr(a, 'command', None) == 'test'
    if os.environ.get('SSH_CONNECTION'):
        if testing:
            return 'terminal'
        raise ValueError('SSH cannot select your local terminal; specify --target')
    term = os.environ.get('TERM', '')
    if os.environ.get('TMUX'):
        # Inherited KITTY_WINDOW_ID can belong to the terminal which started
        # the server, rather than the client currently viewing this session.
        try:
            session = subprocess.run(
                ['tmux', 'display-message', '-p', '-t', os.environ.get('TMUX_PANE', ''), '#{session_id}'],
                check=True, capture_output=True, text=True, timeout=2).stdout.strip()
            clients = subprocess.run(
                ['tmux', 'list-clients', '-t', session, '-F', '#{client_termname}'],
                check=True, capture_output=True, text=True, timeout=2).stdout.splitlines()
            terms = set(clients) - {''}
            if len(terms) != 1:
                raise ValueError('tmux clients have ambiguous terminal types')
            term = terms.pop()
        except (OSError, subprocess.SubprocessError, ValueError):
            if testing:
                return 'terminal'
            raise ValueError('cannot identify tmux client; specify --target kitty|console|firefox') from None
    elif os.environ.get('KITTY_WINDOW_ID'):
        return 'kitty'
    if term == 'linux':
        return 'console'
    if term == 'xterm-kitty':
        return 'kitty'
    if testing:
        return 'terminal'
    raise ValueError('cannot identify target; specify --target kitty|console|firefox')

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
    sections = ''
    for name, lines in rows.items():
        content = 'Latin reference: ABC abc 0123 café\n' + '\n'.join(lines)
        codes = ' '.join(f'U+{ord(c):04X}' for c in sorted(set(content)-{'\n', ' '}, key=ord))
        sections += f'<section><h2>{html.escape(name)}</h2><div class="pair"><pre>{html.escape(content)}</pre><pre class="candidate">{html.escape(content)}</pre></div><details><summary>Codepoints</summary>{codes}</details></section>'
    page = '''<!doctype html><meta charset="utf-8"><title>Agentoo font preview</title>
<style>body{margin:2rem;font:16px system-ui;background:#f5f4ef;color:#222}label{margin-right:1rem}section{border-top:1px solid #aaa;margin-top:2rem}.pair{display:grid;grid-template-columns:1fr 1fr;gap:2rem;overflow:auto}pre{font:20px monospace;line-height:1.7;white-space:pre-wrap}details{overflow-wrap:anywhere}header{position:sticky;top:0;background:#f5f4ef;padding:1rem 0}select,input{font:inherit;max-width:24rem}</style>
<header><h1>Agentoo font preview</h1><label>Candidate <input id="font" list="fonts"></label><datalist id="fonts">OPTIONS</datalist><label>Size <input id="size" type="number" value="20" min="6" max="96"></label><label>Role <select id="role"><option>monospace</option><option>sans-serif</option><option>serif</option></select></label><label><input id="fallback" type="checkbox">Fallback after current default</label><p>Left: current generic font. Right: candidate stack. Latin reference: ABC abc 0123 café.</p><p>Preview only; no Firefox preferences are changed. Use Firefox Inspector → Fonts to inspect actual rendered fonts.</p></header>SECTIONS
<script>const f=document.querySelector('#font'),s=document.querySelector('#size'),r=document.querySelector('#role'),b=document.querySelector('#fallback');f.value=INITIAL;function update(){let quoted='"'+f.value.replaceAll('\\\\','\\\\\\\\').replaceAll('"','\\\\"')+'"';let stack=f.value?(b.checked?r.value+', '+quoted:quoted+', '+r.value):r.value;document.querySelectorAll('pre').forEach(p=>{p.style.fontSize=s.value+'px';p.style.fontFamily=p.classList.contains('candidate')?stack:r.value});}for(let e of [f,s,r,b])e.addEventListener('input',update);update();</script>'''
    page = page.replace('OPTIONS', options).replace('SECTIONS', sections).replace('INITIAL', json.dumps(font or '').replace('<', '\\u003c'))
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


def profile(a):
    bases = [config_home()/'mozilla/firefox', Path.home()/'.mozilla/firefox']
    choices = []
    defaults = set()
    for base in bases:
        ini = configparser.ConfigParser()
        ini.read(base/'profiles.ini')
        for sec in ini.sections():
            if sec.startswith('Install') and ini.has_option(sec, 'Default'):
                defaults.add((base/ini[sec]['Default']).resolve())
            if sec.startswith('Profile'):
                p = Path(ini[sec]['Path'])
                if ini[sec].get('IsRelative', '1') == '1':
                    p = base/p
                choices.append((ini[sec]['Name'], p.resolve()))
    if a.profile:
        matches = [p for n,p in choices if n == a.profile or str(p) == a.profile]
    else:
        matches = [p for n,p in choices if p in defaults] or [p for n,p in choices]
    matches = list(dict.fromkeys(matches))
    if len(matches) != 1:
        raise ValueError('select --profile NAME: ' + ', '.join(n for n,p in choices))
    return matches[0]

def prefs(path):
    result = {}
    for file in ('prefs.js', 'user.js'):
        for m in re.finditer(r'user_pref\(("(?:[^"\\]|\\.)*"),\s*("(?:[^"\\]|\\.)*"|true|false|[0-9]+)\);', read(path/file)):
            result[json.loads(m[1])] = json.loads(m[2])
    return result

def firefox_pref(a, key, value):
    p = profile(a)
    # Firefox holds this symlink for the lifetime of a profile on Linux.
    if (p/'lock').is_symlink() or (p/'.parentlock').is_symlink():
        raise ValueError(f'close Firefox using {p} before changing preferences')
    before = prefs(p).get(key)
    file = p/'user.js'
    text = read(file)
    pattern = r'^user_pref\(' + re.escape(json.dumps(key)) + r',.*\);\s*$'
    text = re.sub(pattern, '', text, flags=re.M).rstrip()
    if value is None:
        # Also clear persisted prefs.js so removing user.js does not leave an old value.
        pf = p/'prefs.js'
        write(pf, re.sub(pattern, '', read(pf), flags=re.M))
    else:
        text += '\nuser_pref(' + json.dumps(key) + ', ' + json.dumps(value, ensure_ascii=False) + ');'
    write(file, text.lstrip('\n') + ('\n' if text else ''))
    print(f'Firefox {p.name}: {key} = {value!r}; takes effect on next start.')
    undo('preference', key, '--target', 'firefox', '--profile', str(p), *(['--clear'] if before is None else ['--value', json.dumps(before, ensure_ascii=False)]))


def kitty_paths():
    base = config_home()/'kitty'
    return base/'kitty.conf', base/'agentoo-fonts.conf'

def kitty_set(a, clear=False):
    config, fragment = kitty_paths()
    original = read(fragment)
    before = read(config)
    if clear:
        write(fragment, '')
    else:
        lines = original.splitlines()
        keys = {'font_family', 'bold_font', 'italic_font', 'bold_italic_font'} if a.font else set()
        if a.size is not None:
            keys.add('font_size')
        lines = [l for l in lines if not l.split() or l.split()[0] not in keys]
        if a.font:
            spec = 'family=' + shlex.quote(a.font)
            if a.style:
                spec += ' style=' + shlex.quote(a.style)
            lines += ['font_family ' + spec, 'bold_font auto', 'italic_font auto', 'bold_italic_font auto']
        if a.size is not None:
            lines.append('font_size ' + str(a.size))
        write(fragment, '\n'.join(lines)+'\n')
        include = 'include agentoo-fonts.conf'
        if include not in before.splitlines():
            write(config, before.rstrip()+'\n\n# Font selections made by agentoo fonts\n'+include+'\n')
    print(f'Updated {fragment}. Reload Kitty configuration or open a new window.')
    print('Later includes, overrides, or command-line options may supersede this fragment.')
    undo('kitty-config', '--value', original)

def console_device(a):
    device = a.console
    if device:
        if not re.fullmatch(r'/dev/tty[0-9]+', device):
            raise ValueError('--console must be /dev/ttyN')
        return device
    if not sys.stdin.isatty() or os.environ.get('TERM') != 'linux':
        raise ValueError('run outside tmux on a Linux console, or specify --console /dev/ttyN')
    return os.ttyname(sys.stdin.fileno())

def root_run(*args):
    return run(*(([] if os.geteuid() == 0 else ['sudo']) + list(args)))

def accept():
    if not sys.stdin.isatty():
        raise ValueError('preview requires an interactive terminal')
    print('\n[a] accept and save / [r] or Escape revert (Ctrl+C also reverts)', flush=True)
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        while True:
            c = os.read(fd, 1)
            if c in (b'a', b'A'):
                return True
            if c in (b'r', b'R', b'\x1b', b'\x03', b''):
                return False
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        print()

def console_set(a):
    if not re.fullmatch(r'[A-Za-z0-9_./+-]+', a.font):
        raise ValueError('invalid console font name')
    if a.size or a.style:
        raise ValueError('console font determines its own size/style')
    device = console_device(a)
    conf = Path('/etc/vconsole.conf')
    old = re.search(r'^FONT=(.*)$', read(conf), re.M)
    if a.command == 'preview':
        if not sys.stdin.isatty():
            raise ValueError('preview requires an interactive terminal')
        with tempfile.TemporaryDirectory(prefix='agentoo-console-') as d:
            backup = Path(d)/'font.psf'
            root_run('setfont', '-C', device, '-O', str(backup))
            accepted = False
            def interrupted(signum, frame):
                raise KeyboardInterrupt
            handlers={sig: signal.signal(sig, interrupted) for sig in (signal.SIGTERM, signal.SIGHUP)}
            try:
                root_run('setfont', '-C', device, a.font)
                terminal_test(a)
                accepted = accept()
            finally:
                try:
                    root_run('setfont', '-C', device, str(backup))
                finally:
                    for sig, handler in handlers.items(): signal.signal(sig, handler)
            if not accepted:
                print('Preview reverted.')
                return
    # Persist only after a successful load; preserve unrelated console settings.
    root_run('setfont', '-C', device, a.font)
    text = re.sub(r'^FONT=.*\n?', '', read(conf), flags=re.M).rstrip()
    text += '\nFONT=' + a.font + '\n'
    with tempfile.NamedTemporaryFile(mode='w') as f:
        f.write(text.lstrip('\n')); f.flush()
        root_run('install', '-m', '0644', f.name, str(conf))
    print('Console font applied and saved in /etc/vconsole.conf.')
    if old:
        undo('set', old[1].strip('"\''), '--target', 'console', '--console', device)
    else:
        undo('console-default', '--console', device)
        print('This restores the boot default, which may differ from a manually loaded previous font.')


def download(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'agentoo-fonts', 'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(req, timeout=90) as response:
        return response.read()

def install_fonts(a):
    if a.font in PACKAGES:
        if a.command == 'remove':
            raise ValueError('manage removal of Gentoo font packages with Portage')
        root_run('emerge', '--ask', PACKAGES[a.font])
        return
    if a.font not in CATALOG:
        raise ValueError('unknown catalog entry; see list --available')
    base = Path('/usr/local/share/fonts/agentoo') if a.system else Path(os.environ.get('XDG_DATA_HOME', str(Path.home()/'.local/share')))/'fonts/agentoo'
    dest = base/(a.font+'-'+a.variant)
    if a.system and os.geteuid() != 0:
        root_run(sys.executable, str(Path(__file__).resolve()), a.command, a.font, '--system', '--variant', a.variant)
        return
    if a.command == 'remove':
        if not (dest/'agentoo-install.json').is_file():
            raise ValueError('not an Agentoo-managed installation')
        print('Check fonts status for active selections before removal.')
        if input(f'Remove {dest}? [y/N] ').lower() != 'y':
            return
        shutil.rmtree(dest)
        run('fc-cache', '-f')
        return
    release = json.loads(download('https://api.github.com/repos/ryanoasis/nerd-fonts/releases/latest'))
    assets = release['assets']
    asset = next((x for x in assets if x['name'] == CATALOG[a.font]+'.zip'), None)
    if not asset:
        raise ValueError('latest release does not contain requested archive')
    print(f'Downloading {asset["name"]} ({release["tag_name"]})', flush=True)
    blob = download(asset['browser_download_url'])
    digest = asset.get('digest')
    if not digest:
        checks = next((x for x in assets if 'sha256' in x['name'].lower()), None)
        if checks:
            for line in download(checks['browser_download_url']).decode().splitlines():
                parts = line.split()
                if len(parts) == 2 and parts[1].lstrip('*').split('/')[-1] == asset['name']:
                    digest = 'sha256:'+parts[0]
    if digest:
        if digest != 'sha256:'+hashlib.sha256(blob).hexdigest():
            raise ValueError('upstream checksum mismatch; nothing installed')
        print('SHA-256 verified against official release metadata.')
    else:
        print('No upstream checksum available; downloaded over HTTPS. SHA-256: '+hashlib.sha256(blob).hexdigest())
    base.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=base, prefix='.font-stage-') as temp:
        stage = Path(temp)/'new'; stage.mkdir(mode=0o755); stage.chmod(0o755)
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            for member in archive.infolist():
                name = Path(member.filename).name
                if member.is_dir():
                    continue
                if name.lower().endswith(('.ttf', '.otf')):
                    variant = 'propo' if 'NerdFontPropo' in name else 'mono' if 'NerdFontMono' in name else 'standard'
                    if a.font != 'symbols' and variant != a.variant:
                        continue
                elif not any(x in name.lower() for x in ('license', 'copying', 'ofl', 'readme')):
                    continue
                if member.file_size > 100*1024*1024:
                    raise ValueError('unexpectedly large archive member')
                if (stage/name).exists():
                    raise ValueError('duplicate font filename in archive')
                (stage/name).write_bytes(archive.read(member))
                (stage/name).chmod(0o644)
        if not list(stage.glob('*.ttf')) and not list(stage.glob('*.otf')):
            raise ValueError('archive contains no fonts for requested variant')
        write(stage/'agentoo-install.json', json.dumps({'catalog':a.font,'version':release['tag_name'],'variant':a.variant,'sha256':hashlib.sha256(blob).hexdigest()}, indent=2)+'\n')
        if dest.exists():
            if not (dest/'agentoo-install.json').is_file():
                raise ValueError('refusing to replace unmanaged directory')
            previous = Path(temp)/'previous'
            dest.rename(previous)
            try:
                stage.rename(dest)
            except BaseException:
                previous.rename(dest)
                raise
        else:
            stage.rename(dest)
    run('fc-cache', '-f', str(dest))
    print('Installed; no target selection changed. Families:')
    print(output('fc-scan', '--format=%{family}\n', *sorted(dest.glob('*.ttf')), *sorted(dest.glob('*.otf'))))

def main():
    parser = argparse.ArgumentParser(
        prog='agentoo fonts', description=__doc__,
        epilog='With no command, show status. Start with: agentoo fonts test\n'
               'Use agentoo fonts COMMAND --help for arguments and examples.',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', title='commands', metavar='COMMAND',
                                help='operation to perform (default: status)')
    def command(name, description, *, targets=False, profiles=False, examples=''):
        p = sub.add_parser(name, help=description, description=description,
                           epilog=examples or None,
                           formatter_class=argparse.RawDescriptionHelpFormatter)
        p.set_defaults(target='auto', profile=None, style=None, console=None)
        if targets:
            p.add_argument('--target', choices=('auto','kitty','console','firefox'), default='auto',
                           help='target application (default: auto detects Kitty/Linux console, including tmux clients; Firefox must be explicit)')
        if profiles:
            p.add_argument('--profile', metavar='NAME_OR_PATH',
                           help='Firefox profile name or absolute path; default: unambiguous installation-default profile; changes require that profile closed')
        return p
    def role_options(p):
        p.add_argument('--role', choices=ROLES, default='monospace',
                       help='Firefox font role (default: monospace); leaves other roles unchanged')
        p.add_argument('--script', default='x-western', metavar='GROUP',
                       help='Firefox script/language preference group (default: x-western); e.g. x-unicode or el for Greek')
    def size_option(p):
        p.add_argument('--size', type=float, metavar='POINTS',
                       help='Kitty only: font size, 4–96 points; default: keep existing size')
    def console_option(p):
        p.add_argument('--console', metavar='/dev/ttyN',
                       help='Linux console device; default: current real console outside tmux; console operations request sudo as needed')
    command('status', 'Report configuration; running overrides may differ', targets=True, profiles=True,
            examples='Examples:\n  agentoo fonts status\n  agentoo fonts status --target firefox')
    p = command('list', 'List installed font families/faces or the installation catalog',
                examples='Examples:\n  agentoo fonts list --nerd\n  agentoo fonts list --available --family ubuntu')
    p.add_argument('--available', action='store_true', help='show installable catalog entries instead of installed families')
    p.add_argument('--nerd', action='store_true', help='show only Nerd Font families/catalog entries')
    p.add_argument('--family', default='', metavar='TEXT', help='case-insensitive substring filter (default: no filter)')
    suites = ('smoke','nerd','greek','borders','braille','unicode','emoji','kaomoji','width','all')
    suite_help = ('sample collection (default: all): smoke=styles/code/icons; nerd=icon spacing; '
                  'greek=polytonic/composing marks; borders=thin/heavy/double lines; '
                  'braille=spinners/dots; unicode=symbols/CJK/combining marks; '
                  'emoji=joined/color sequences; kaomoji=text faces; width=terminal ruler; '
                  'all=all collections except width')
    for name in ('test','preview'):
        p = command(name,
                    'Display visual samples without changing font settings' if name == 'test' else
                    'Try an installed font; a accepts/saves, r/Escape/Ctrl+C reverts',
                    targets=True, profiles=(name == 'preview'),
                    examples=('Examples:\n  agentoo fonts test\n  agentoo fonts test nerd --codepoints\n'
                              '  agentoo fonts test greek --target firefox\n'
                              '  agentoo fonts test all --target firefox --no-open --output /tmp/fonts.html\n\n'
                              'Unrecognized/SSH terminals still display samples locally. Firefox requires\n'
                              '--target firefox. Visual output is not an automated coverage result.') if name == 'test' else
                             ('Examples:\n  agentoo fonts preview "UbuntuSansMono Nerd Font" --target kitty --size 12\n'
                              '  agentoo fonts preview ter-v24n --target console\n'
                              '  agentoo fonts preview "Noto Sans" --target firefox --fallback\n\n'
                              'Kitty opens a separate preview window. Console temporarily saves/restores\n'
                              'the loaded font. Firefox opens HTML: close Firefox, then accept/revert in\n'
                              'the terminal. Acceptance saves the command-line family/role/script, not\n'
                              'HTML control adjustments. No persistent backups; saves print revert commands.'))
        if name == 'test':
            p.add_argument('suite', choices=suites, nargs='?', default='all', help=suite_help)
        else:
            p.add_argument('font', metavar='FONT', help='installed graphical family name (quote spaces), or console PSF font name/path; use list or choose to discover fonts')
            p.add_argument('--suite', choices=suites, default='all', help=suite_help)
            role_options(p)
            p.add_argument('--fallback', action='store_true', help='Firefox only: accept into the script/role fallback list instead of replacing its primary font')
            console_option(p)
            size_option(p)
            p.add_argument('--style', metavar='STYLE', help='Kitty only: face style, e.g. Medium; default: family default')
        p.add_argument('--codepoints', action='store_true', help='terminal only: append detailed codepoint tables to each group; default: hidden (Firefox uses expandable details)')
        p.add_argument('--columns', type=int, default=6, metavar='N', help='terminal codepoint table columns, 1–6 (default: 6); does not set terminal width')
        p.add_argument('--plain', action='store_true', help='terminal only: omit ANSI style demonstration; Unicode samples remain')
        p.add_argument('--output', metavar='FILE', help='Firefox only: write HTML here; default: $XDG_CACHE_HOME/agentoo/fonts/preview.html or ~/.cache/agentoo/fonts/preview.html')
        p.add_argument('--no-open', action='store_true', help='Firefox only: generate HTML without launching browser or accepting changes')
    p = command('set', 'Apply and persist a font selection; print the revert command', targets=True, profiles=True,
                examples='Examples:\n  agentoo fonts set "Liberation Mono" --target kitty --size 11\n  agentoo fonts set ter-v24n --target console\n  agentoo fonts set "Liberation Mono" --target firefox --role monospace\n\nKitty: reload configuration after saving. Firefox: close profile before saving;\nchanges apply on next start. Console: apply immediately and persist FONT.')
    p.add_argument('font', metavar='FONT', help='graphical family name (quote spaces), or console PSF font name/path')
    size_option(p)
    p.add_argument('--style', metavar='STYLE', help='Kitty only: face style, e.g. Medium; default: family default')
    console_option(p)
    role_options(p)
    p = command('size', 'Persist Kitty font size; reload Kitty configuration to apply', targets=True,
                examples='Example:\n  agentoo fonts size 12 --target kitty\n\nOnly Kitty is supported. Console size is part of the selected bitmap font.')
    p.add_argument('size', type=float, metavar='POINTS', help='Kitty font size, 4–96 points')
    p.set_defaults(font=None)
    command('choose', 'Open Kitty chooser, list console font files, or open Firefox samples', targets=True,
            examples='Examples:\n  agentoo fonts choose --target kitty\n  agentoo fonts choose --target console\n\nKitty chooser saves a user font fragment; reload configuration to apply.\nConsole lists available files for preview/set. Firefox opens a visual page only.')
    for name in ('install','remove'):
        p = command(name, 'Install latest official Nerd Fonts or a curated Gentoo font package' if name == 'install' else
                    'Remove an Agentoo-managed Nerd Font entry after confirmation',
                    examples=('Examples:\n  agentoo fonts install ubuntu-sans-mono\n'
                              '  agentoo fonts install fira-code --variant mono --system\n'
                              '  agentoo fonts install noto-emoji\n\n'
                              'Use list --available for catalog IDs. Nerd Fonts install per-user by default;\n'
                              'Gentoo packages always install system-wide via emerge --ask. Downloads use\n'
                              'the latest official release and verify upstream checksums when available.\n'
                              'Installation does not activate a font.') if name == 'install' else
                             ('Example:\n  agentoo fonts remove fira-code --variant mono\n\n'
                              'Check active selections before removal. Only manifest-bearing Agentoo\n'
                              'directories are removed; Gentoo packages must be removed through Portage.'))
        p.add_argument('font', metavar='NAME', help='catalog ID from list --available (not the installed family name)')
        p.add_argument('--system', action='store_true', help='use /usr/local/share/fonts/agentoo and request sudo as needed; default: $XDG_DATA_HOME/fonts/agentoo or ~/.local/share/fonts/agentoo')
        p.add_argument('--variant', choices=('standard','mono','propo'), default='standard', help='Nerd Fonts variant: standard=regular icon sizing, mono=single-cell icons, propo=proportional icons (default: standard); not used for Gentoo packages; symbols entry includes all variants')
    p = command('fallback', 'Inspect/edit Firefox script/role fallback lists without changing primary preferences', targets=True, profiles=True,
                examples='Examples:\n  agentoo fonts fallback show --target firefox\n  agentoo fonts fallback add "Symbols Nerd Font" --target firefox\n  agentoo fonts fallback remove "Symbols Nerd Font" --target firefox\n\nRequires --target firefox. Close the profile before changes. Explicit lists\nreplace the built-in list for that role/script; primary preferences stay intact.\nWebsite CSS, privacy settings, and existing primary glyphs can affect results.')
    p.add_argument('operation', choices=('show','add','remove'), help='show current explicit list, append a family, or remove a family')
    p.add_argument('font', nargs='?', metavar='FONT', help='family name, required for add/remove; omit for show')
    role_options(p)
    p = command('coverage', 'Check sample codepoints in one fontconfig-selected face; not visual rendering',
                examples='Example:\n  agentoo fonts coverage "Liberation Mono" --suite greek\n\nReports the matched face (which may be a substitute). Does not test fallback,\nshaping, ligatures, or emoji sequence appearance.')
    p.add_argument('font', metavar='FONT', help='installed family name or fontconfig pattern')
    p.add_argument('--suite', choices=suites, default='all', help=suite_help)
    p = command('explain', 'Show Unicode codepoints and fontconfig candidate fonts',
                examples='Example:\n  agentoo fonts explain "ᾧ" --font "Liberation Mono"\n\nCandidate lists do not prove which font Firefox or Kitty actually rendered.')
    p.add_argument('character', metavar='TEXT', help='one or more characters to inspect; quote spaces or shell punctuation')
    p.add_argument('--font', default='monospace', metavar='PATTERN', help='fontconfig family/pattern to query (default: monospace)')
    p = command('preference', 'Set/clear an exact Firefox font preference, mainly for printed revert commands', targets=True, profiles=True,
                examples='Requires --target firefox and a closed profile. --value takes JSON, so a\nstring needs JSON quotes inside shell quotes. Prefer the printed revert command.')
    p.add_argument('key', metavar='KEY', help='Firefox preference name beginning with font.')
    g=p.add_mutually_exclusive_group(required=True)
    g.add_argument('--value', metavar='JSON', help='exact preference value encoded as JSON, e.g. \'"Liberation Mono"\'')
    g.add_argument('--clear', action='store_true', help='remove explicit preference from user.js and prefs.js, restoring Firefox defaults')
    p = command('kitty-config', 'Restore exact Agentoo user font fragment from a printed revert command',
                examples='Use the complete printed revert command; --value may contain newlines.\nLeaves the include in kitty.conf intact. Reload Kitty configuration afterward.')
    p.add_argument('--value', required=True, metavar='TEXT', help='complete previous fragment contents; empty string clears Agentoo selections')
    p = command('console-default', 'Clear persistent FONT and reset the active console to its boot font',
                examples='Example:\n  agentoo fonts console-default --console /dev/tty1\n\nRequests sudo as needed. Boot font may differ from a previously manually loaded\nfont; this does not restore a saved font snapshot.')
    console_option(p)
    a = parser.parse_args()
    if a.command is None:
        a.command = 'status'; a.target = 'auto'; a.profile = None
    if getattr(a,'columns',1) < 1 or getattr(a,'columns',1) > 6:
        parser.error('--columns must be between 1 and 6')
    if getattr(a,'size',None) is not None and not (4 <= a.size <= 96):
        parser.error('size must be between 4 and 96 points')
    if getattr(a,'font',None) and any(c in a.font for c in '\r\n\0'):
        parser.error('font must be a single line')
    if a.command == 'list':
        if a.available:
            for key,val in CATALOG.items():
                if a.family.lower() in (key+' '+val).lower(): print(f'{key:22} {val} — latest official Nerd Fonts release')
            if not a.nerd:
                for name, package in PACKAGES.items():
                    if a.family.lower() in name: print(f'{name:22} {package} — Gentoo system package')
        else:
            for line in sorted(set(output('fc-list','--format=%{family}\t%{style}\n').splitlines())):
                if a.family.lower() in line.lower() and (not a.nerd or 'nerd' in line.lower()): print(line)
        return
    if a.command in ('install','remove'):
        install_fonts(a); return
    if a.command == 'status':
        print(f'TERM={os.environ.get("TERM","unset")} tmux={bool(os.environ.get("TMUX"))} SSH={bool(os.environ.get("SSH_CONNECTION"))}')
        t = target(a)
        print('Target:',t)
        if t == 'kitty':
            for p in (Path('/etc/xdg/kitty/kitty.conf'), *kitty_paths()):
                print(f'\n{p}:\n{read(p) or "(absent)"}')
            print('Fontconfig monospace candidate:',output('fc-match','monospace'))
            print('Runtime fonts and command-line/host overrides are not established by this report.')
        elif t == 'console':
            print(read(Path('/etc/vconsole.conf')) or '(no vconsole.conf)')
            print('Active font name cannot be inferred from configuration. Save dimensions/map with:')
            print('sudo setfont -v -O /tmp/agentoo-current-console-font.psf')
        else:
            p=profile(a); print(p)
            for k,v in sorted(prefs(p).items()):
                if k.startswith('font.') or k == 'browser.display.use_document_fonts': print(k,'=',v)
            print('Only explicit preferences shown; webpage CSS and fallback can select other fonts.')
        return
    if a.command == 'coverage':
        record=output('fc-match','--format=%{family}\n%{file}\n%{charset}',a.font).splitlines()
        if len(record) < 3: raise ValueError('fontconfig returned no character set')
        covered=set()
        for part in record[2].split():
            bounds=part.split('-'); start=int(bounds[0],16); end=int(bounds[-1],16)
            covered.update(range(start,end+1))
        print('Matched face:',record[0],record[1])
        chars=set(''.join(s for rows in samples(a.suite).values() for s in rows))-set(' \n')
        missing=sorted((c for c in chars if ord(c) not in covered),key=ord)
        print(f'{len(chars)-len(missing)}/{len(chars)} distinct sample codepoints present in this face.')
        for c in missing: print(f'Missing U+{ord(c):04X} {unicodedata.name(c,"unnamed")}')
        print('Fallback, composition, shaping, and appearance require visual inspection.')
        return
    if a.command == 'explain':
        for c in a.character:
            print(f'{c!r} U+{ord(c):04X} {unicodedata.name(c,"unnamed")}')
            print(output('fc-match','-s','--format=%{family}\t%{file}\n',f'{a.font}:charset={ord(c):x}'))
        print('Fontconfig candidates are not proof of the font actually rendered in Firefox/Kitty.')
        return
    if a.command == 'kitty-config':
        write(kitty_paths()[1], a.value); print('Restored user fragment. Reload Kitty configuration.'); return
    if a.command == 'console-default':
        device=console_device(a)
        root_run('setfont','-C',device,'-R')
        text=re.sub(r'^FONT=.*\n?', '',read(Path('/etc/vconsole.conf')),flags=re.M)
        with tempfile.NamedTemporaryFile(mode='w') as f:
            f.write(text); f.flush(); root_run('install','-m','0644',f.name,'/etc/vconsole.conf')
        return
    t=target(a)
    if a.command == 'test':
        if t == 'firefox': browser_test(a)
        else: terminal_test(a)
        return
    if a.command == 'choose':
        if t == 'kitty':
            config,fragment=kitty_paths()
            if not fragment.exists(): write(fragment,'')
            previous=read(fragment)
            try:
                run('kitten','choose-fonts','--config-file-name',str(fragment),'--reload-in','none')
                if read(fragment) != previous:
                    text=read(config)
                    if 'include agentoo-fonts.conf' not in text.splitlines(): write(config,text.rstrip()+'\ninclude agentoo-fonts.conf\n')
                    undo('kitty-config','--value',previous)
            except BaseException:
                write(fragment,previous); raise
        elif t == 'console':
            print(output('find','/usr/share/consolefonts','-type','f'))
            print('Use: agentoo fonts preview NAME --target console')
        else:
            a.suite='all'; a.output=None; a.no_open=False; browser_test(a)
        return
    if a.command in ('fallback','preference'):
        if t != 'firefox': raise ValueError('this command requires --target firefox')
        if a.command == 'preference':
            if not a.key.startswith('font.'):
                raise ValueError('only font.* preferences are supported')
            firefox_pref(a,a.key,None if a.clear else json.loads(a.value)); return
        key=f'font.name-list.{a.role}.{a.script}'
        previous=prefs(profile(a)).get(key,'')
        if a.operation == 'show': print(key,'=',previous or '(Firefox built-in fallback)'); return
        if not a.font: raise ValueError('specify a font family')
        if not isinstance(previous,str): raise ValueError('unexpected non-string fallback preference')
        families=[x.strip() for x in previous.split(',') if x.strip()]
        if a.operation == 'add' and a.font not in families: families.append(a.font)
        if a.operation == 'remove': families=[x for x in families if x != a.font]
        print('Changes only this explicit script/role list; built-in fallback may differ. Primary font preferences remain unchanged.')
        firefox_pref(a,key,', '.join(families) if families else None); return
    if a.command == 'preview':
        if t == 'console': console_set(a)
        elif t == 'firefox':
            browser_test(a,a.font)
            if not a.no_open:
                print('Close Firefox before accepting in this terminal. HTML adjustments are visual only; acceptance saves the command-line family/role/script.')
                if accept():
                    if a.fallback:
                        key=f'font.name-list.{a.role}.{a.script}'
                        families=[x.strip() for x in prefs(profile(a)).get(key,'').split(',') if x.strip()]
                        if a.font not in families: families.append(a.font)
                        firefox_pref(a,key,', '.join(families))
                    else:
                        firefox_pref(a,f'font.name.{a.role}.{a.script}',a.font)
                else: print('Preview closed without changing Firefox preferences.')
        else:
            if not shutil.which('kitty'): raise ValueError('kitty not installed')
            cmd=['kitty','--class','agentoo-font-preview','-o','font_family='+('family='+shlex.quote(a.font)+((' style='+shlex.quote(a.style)) if a.style else ''))]
            if a.size: cmd+=['-o',f'font_size={a.size}']
            cmd += [sys.executable, str(Path(__file__).resolve()), '_kitty-preview']
            env=os.environ.copy(); env['AGENTOO_PREVIEW']=json.dumps({'font':a.font,'size':a.size,'style':a.style,'suite':a.suite,'columns':a.columns,'plain':a.plain,'codepoints':a.codepoints})
            run(*cmd,env=env)
        return
    if a.command in ('set','size'):
        if t == 'kitty': kitty_set(a)
        elif t == 'console':
            if a.command == 'size': raise ValueError('console size is determined by the font; select another font')
            if a.size or a.style: raise ValueError('console font determines its own size/style')
            if not re.fullmatch(r'[A-Za-z0-9_./+-]+',a.font): raise ValueError('invalid console font name')
            console_set(a)
        else:
            if a.command == 'size': raise ValueError('size currently supports Kitty only')
            if a.style or a.size: raise ValueError('Firefox selection supports family/role/script; size/style are not supported here')
            firefox_pref(a,f'font.name.{a.role}.{a.script}',a.font)

if __name__ == '__main__':
    try:
        if sys.argv[1:] == ['_kitty-preview']:
            a=argparse.Namespace(**json.loads(os.environ['AGENTOO_PREVIEW']))
            terminal_test(a)
            if accept(): kitty_set(a)
            else: print('Preview reverted; original Kitty configuration unchanged.')
        else:
            main()
    except (ValueError,OSError,subprocess.CalledProcessError,KeyError,zipfile.BadZipFile) as error:
        print(f'agentoo fonts: {error}',file=sys.stderr); sys.exit(2)
    except KeyboardInterrupt:
        print('\nCancelled.',file=sys.stderr); sys.exit(130)
