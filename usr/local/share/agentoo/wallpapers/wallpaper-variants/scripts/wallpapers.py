#!/usr/bin/env python3
"""Version wallpaper edits, export PNG/JPEG collections, and build review galleries."""
import argparse
from datetime import datetime, timezone
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from PIL import Image, JpegImagePlugin, __version__ as pillow_version

EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.tif', '.tiff', '.avif', '.jxl'}


def dimensions(path):
    with Image.open(path) as image:
        size = list(image.size)
        image.verify()
    return size


def size_arg(value):
    match = re.fullmatch(r'([1-9]\d*)[x×]([1-9]\d*)', value)
    if not match:
        raise argparse.ArgumentTypeError('Expected WIDTHxHEIGHT, for example 6144x2560')
    return [int(x) for x in match.groups()]


def key(size):
    return f'{size[0]}x{size[1]}'


def save(job, manifest):
    temporary = job / 'manifest.json.tmp'
    temporary.write_text(json.dumps(manifest, indent=2) + '\n')
    temporary.replace(job / 'manifest.json')


def read(job):
    manifest = json.loads((job / 'manifest.json').read_text())
    if manifest.get('schema') != 1:
        raise ValueError('Unsupported wallpaper job schema')
    return manifest


def ffmpeg(source, destination, filters):
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin',
                    '-n', '-i', str(source), '-vf', filters, '-frames:v', '1',
                    '-threads', '1', str(destination)], check=True)


def thumbnail(job, source, destination):
    if not (job / destination).exists():
        ffmpeg(job / source, job / destination,
               'scale=640:400:force_original_aspect_ratio=decrease:flags=lanczos')
    return destination


def init(args):
    job, source = args.output.resolve(), args.source.expanduser().resolve()
    if (job / 'manifest.json').exists():
        raise ValueError('Job already exists; resume with add/build/select')
    if job.exists() and any(job.iterdir()):
        raise ValueError('Choose an empty output folder')
    sizes = args.sizes
    if sizes is None:
        readme = Path(__file__).resolve().parents[2] / 'README.md'
        if not readme.exists():
            raise ValueError('Wallpaper README unavailable; supply --sizes')
        sizes = [[int(w), int(h)] for w, h in re.findall(
            r'\|\s*(\d+)\s*×\s*(\d+)\s*\|', readme.read_text())]
    sizes = list(dict.fromkeys(tuple(s) for s in sizes))
    if not sizes:
        raise ValueError('No target dimensions found; supply --sizes')
    masters, ids = [], set()
    for path in sorted(source.iterdir()):
        if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
            continue
        master_id = re.sub(r'[^a-z0-9]+', '-', path.stem.lower()).strip('-')
        if not master_id or master_id in ids:
            raise ValueError(f'Empty or duplicate master ID for {path.name}; rename the source')
        ids.add(master_id)
        masters.append({'id': master_id, 'name': path.name, 'original_path': str(path),
                        'size': dimensions(path),
                        'file': f'originals/{master_id}{path.suffix.lower()}'})
    if not masters:
        raise ValueError('No supported wallpaper images found in source folder')
    job.mkdir(parents=True, exist_ok=True)
    (job / 'originals').mkdir()
    for master in masters:
        shutil.copy2(master['original_path'], job / master['file'])
    manifest = {'schema': 1, 'created': datetime.now(timezone.utc).isoformat(),
                'targets': sizes, 'masters': masters, 'variants': {}}
    save(job, manifest)
    build(job, manifest)
    print('Master IDs: ' + ', '.join(m['id'] for m in masters))


def variant(manifest, master_id, target):
    if master_id not in {m['id'] for m in manifest['masters']}:
        raise ValueError('Unknown master ID')
    if target not in manifest['targets']:
        raise ValueError('Target is not in this job')
    return f'{master_id}/{key(target)}'


def add(args):
    job = args.job.resolve()
    manifest = read(job)
    variant_id = variant(manifest, args.master, args.target)
    source = args.image.expanduser().resolve()
    iw, ih = dimensions(source)
    width, height = args.target
    if abs((iw / ih) / (width / height) - 1) > .005:
        raise ValueError('Generated aspect ratio differs by over 0.5%; outpaint again instead of cropping/stretching')
    prompt = args.prompt_file.read_text().strip()
    if not prompt:
        raise ValueError('Generation prompt must not be empty')
    entry = manifest['variants'].setdefault(variant_id, {'selected': None, 'revisions': []})
    revision = max((r['revision'] for r in entry['revisions']), default=0) + 1
    # Preserve even an orphaned artifact from a failed earlier export.
    while (job / f'generated/{variant_id}/v{revision:03d}{source.suffix.lower()}').exists() or (job / f'final/{variant_id}/v{revision:03d}.png').exists():
        revision += 1
    raw = f'generated/{variant_id}/v{revision:03d}{source.suffix.lower()}'
    final = f'final/{variant_id}/v{revision:03d}.png'
    (job / raw).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, job / raw)
    factor = min(width / iw, height / ih)
    sw, sh = min(width, round(iw * factor)), min(height, round(ih * factor))
    left, top = (width - sw) // 2, (height - sh) // 2
    right, bottom = width - sw - left, height - sh - top
    filters = f'scale={sw}:{sh}:flags=lanczos,setsar=1'
    if left or right or top or bottom:
        filters += (f',pad={width}:{height}:{left}:{top},'
                    f'fillborders=left={left}:right={right}:top={top}:bottom={bottom}:mode=smear')
    ffmpeg(job / raw, job / final, filters)
    if dimensions(job / final) != args.target:
        raise ValueError('Export dimensions do not match target')
    entry['revisions'].append({'revision': revision, 'generated': raw,
                              'generated_size': [iw, ih], 'final': final,
                              'prompt': prompt, 'note': args.note,
                              'method': 'Lanczos fit; boundary pixels extend tiny rounding gaps',
                              'created': datetime.now(timezone.utc).isoformat()})
    entry['selected'] = revision
    save(job, manifest)
    build(job, manifest)


def select(args):
    job = args.job.resolve()
    manifest = read(job)
    entry = manifest['variants'].get(variant(manifest, args.master, args.target))
    if entry is None or args.revision not in {r['revision'] for r in entry['revisions']}:
        raise ValueError('Revision does not exist')
    entry['selected'] = args.revision
    save(job, manifest)
    build(job, manifest)


def export_jpeg(args):
    job, destination = args.job.resolve(), args.output.resolve()
    manifest = read(job)
    if not 1 <= args.quality <= 100:
        raise ValueError('JPEG quality must be between 1 and 100')
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('Choose an empty JPEG output folder; earlier exports are preserved')
    selected = []
    for master in manifest['masters']:
        for target in manifest['targets']:
            variant_id = f'{master["id"]}/{key(target)}'
            entry = manifest['variants'].get(variant_id)
            if not entry:
                raise ValueError(f'Complete the PNG target matrix before export; missing {variant_id}')
            record = next(r for r in entry['revisions'] if r['revision'] == entry['selected'])
            source = job / record['final']
            if dimensions(source) != target:
                raise ValueError(f'Wrong PNG dimensions: {source}')
            selected.append((master, target, record, source))
    destination.mkdir(parents=True, exist_ok=True)
    outputs, cards, total_png = [], [], 0
    current_master = None
    esc = lambda value: html.escape(str(value), quote=True)
    settings = {'quality': args.quality, 'subsampling': 0,
                'optimize': True, 'progressive': False}
    for master, target, record, source in selected:
        name = master['id']
        relative = f'{name}/{name}_{key(target)}.jpg'
        output = destination / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(source) as image:
            if image.has_transparency_data:
                if image.convert('RGBA').getchannel('A').getextrema() != (255, 255):
                    raise ValueError(f'JPEG cannot preserve transparency; choose compositing explicitly: {source}')
            options = dict(settings)
            if image.info.get('icc_profile'):
                options['icc_profile'] = image.info['icc_profile']
            image.convert('RGB').save(output, format='JPEG', **options)
        with Image.open(output) as image:
            image.load()
            if list(image.size) != target or image.format != 'JPEG' or JpegImagePlugin.get_sampling(image) != 0:
                raise ValueError(f'JPEG failed size/format/4:4:4 verification: {output}')
        reference = Path(os.path.relpath(source, destination)).as_posix()
        size, png_size = output.stat().st_size, source.stat().st_size
        total_png += png_size
        revision = record['revision']
        outputs.append({'master': name, 'source_revision': revision, 'source_png': reference,
                        'file': relative, 'dimensions': target, 'bytes': size,
                        'source_png_bytes': png_size})
        preview = thumbnail(destination, relative, f'previews/{name}/{key(target)}.png')
        data = esc(json.dumps({str(revision): {'preview': preview, 'final': relative,
                         'note': f'JPEG quality {args.quality}, 4:4:4 · {size / 2**20:.2f} MiB',
                         'generated': key(record['generated_size'])}}))
        if name != current_master:
            if current_master is not None:
                cards.append('</div></section>')
            cards.append(f'<section data-master="{esc(name)}"><h2>{esc(master["name"])}</h2><div class="grid">')
            current_master = name
        cards.append(f'<article data-target="{key(target)}"><h3>{key(target)}</h3>'
                     f'<p><a href="{esc(reference)}">PNG reference</a> · source revision v{revision:03d}</p>'
                     f'<div class="variant" data-id="{esc(name)}/{key(target)}" data-current="{revision}" data-revisions="{data}">'
                     f'<select aria-label="Source revision"><option value="{revision}">v{revision:03d}</option></select>'
                     f'<a class="full" href="{esc(relative)}"><img loading="lazy" src="{esc(preview)}" alt="{esc(name)} {key(target)}"></a>'
                     f'<p class="generated">Generated source: {key(record["generated_size"])}</p>'
                     f'<p class="note">JPEG quality {args.quality}, 4:4:4 · {size / 2**20:.2f} MiB</p>'
                     '<textarea aria-label="JPEG review feedback" placeholder="What would you change?"></textarea>'
                     '</div></article>')
    if current_master is not None:
        cards.append('</div></section>')
    total = sum(r['bytes'] for r in outputs)
    reduction = 100 * (1 - total / total_png) if total_png else 0
    report = {'format': 'JPEG', 'pillow_version': pillow_version,
              'settings': {**settings, 'chroma_subsampling': '4:4:4'},
              'created': datetime.now(timezone.utc).isoformat(),
              'count': len(outputs), 'total_bytes': total,
              'source_png_total_bytes': total_png, 'reduction_percent': reduction,
              'outputs': outputs}
    (destination / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    summary = f'{len(outputs)} JPEGs · quality {args.quality} · 4:4:4 · {total / 2**20:.2f} MiB · {reduction:.1f}% smaller than selected PNGs'
    template = (Path(__file__).parent.parent / 'assets/gallery.html').read_text()
    template = template.replace('Wallpaper review', 'JPEG wallpaper review')
    template = template.replace('full-resolution PNG', 'full-resolution JPEG')
    template = template.replace('Revision menus preview history; tell your agent which version to keep.',
                                'Each image names its source PNG revision; JPEG compression is lossy.')
    template = template.replace('Manifest &amp; prompts', 'JPEG manifest')
    master_options = ''.join(f'<option value="{esc(m["id"])}">{esc(m["name"])}</option>' for m in manifest['masters'])
    target_options = ''.join(f'<option>{key(t)}</option>' for t in manifest['targets'])
    page = template.replace('<!-- SUMMARY -->', esc(summary)).replace('<!-- MASTERS -->', master_options).replace('<!-- TARGETS -->', target_options).replace('<!-- CARDS -->', '\n'.join(cards))
    (destination / 'index.html').write_text(page)
    print(summary)
    print(destination / 'index.html')


def build(job, manifest):
    selected_bytes, completed = 0, 0
    cards, missing = [], []
    esc = lambda value: html.escape(str(value), quote=True)
    for master in manifest['masters']:
        master_id = master['id']
        thumb = thumbnail(job, master['file'], f'previews/originals/{master_id}.png')
        cards.append(f'<section data-master="{esc(master_id)}"><h2>{esc(master["name"])}</h2>'
                     f'<a href="{esc(master["file"])}"><img class="original" src="{esc(thumb)}" alt="Original"></a>'
                     f'<p>Original: {key(master["size"])} · <a href="{esc(master["file"])}">Open original</a></p><div class="grid">')
        for target in manifest['targets']:
            variant_id = f'{master_id}/{key(target)}'
            entry = manifest['variants'].get(variant_id)
            cards.append(f'<article data-target="{key(target)}"><h3>{key(target)}</h3>')
            if not entry:
                missing.append(variant_id)
                cards.append('<p>Awaiting image</p></article>')
                continue
            options, revisions = [], {}
            for record in entry['revisions']:
                if dimensions(job / record['final']) != target:
                    raise ValueError(f'Wrong dimensions: {record["final"]}')
                number = record['revision']
                preview = thumbnail(job, record['final'], f'previews/{variant_id}/v{number:03d}.png')
                revisions[str(number)] = {'preview': preview, 'final': record['final'],
                                          'note': record['note'], 'generated': key(record['generated_size'])}
                selected = number == entry['selected']
                if selected:
                    selected_bytes += (job / record['final']).stat().st_size
                options.append(f'<option value="{number}" {"selected" if selected else ""}>v{number:03d}{" — selected" if selected else ""}</option>')
            current = revisions[str(entry['selected'])]
            completed += 1
            data = esc(json.dumps(revisions))
            cards.append(f'<div class="variant" data-revisions="{data}" data-id="{esc(variant_id)}" data-current="{entry["selected"]}">'
                         f'<select aria-label="Preview revision" onchange="preview(this)">{"".join(options)}</select>'
                         f'<a class="full" href="{esc(current["final"])}"><img loading="lazy" src="{esc(current["preview"])}" alt="{esc(variant_id)}"></a>'
                         f'<p class="generated">Generated source: {esc(current["generated"])}</p>'
                         f'<p class="note">{esc(current["note"])}</p>'
                         '<textarea aria-label="Revision feedback" placeholder="What would you change?"></textarea>'
                         '</div></article>')
        cards.append('</div></section>')
    expected = len(manifest['masters']) * len(manifest['targets'])
    summary = f'{completed}/{expected} variants · selected final PNGs: {selected_bytes / 2**20:.1f} MiB'
    manifest['summary'] = {'completed': completed, 'expected': expected,
                           'selected_final_bytes': selected_bytes, 'missing': missing}
    save(job, manifest)
    template = (Path(__file__).parent.parent / 'assets/gallery.html').read_text()
    master_options = ''.join(f'<option value="{esc(m["id"])}">{esc(m["name"])}</option>' for m in manifest['masters'])
    target_options = ''.join(f'<option>{key(t)}</option>' for t in manifest['targets'])
    page = template.replace('<!-- SUMMARY -->', esc(summary)).replace('<!-- MASTERS -->', master_options).replace('<!-- TARGETS -->', target_options).replace('<!-- CARDS -->', '\n'.join(cards))
    (job / 'index.html').write_text(page)
    print(summary)
    print(job / 'index.html')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    child = commands.add_parser('init', help='Copy originals, inventory targets, create gallery')
    child.add_argument('--source', type=Path, required=True)
    child.add_argument('--output', type=Path, required=True)
    child.add_argument('--sizes', type=size_arg, nargs='+')
    child.set_defaults(run=init)
    child = commands.add_parser('export-jpeg', help='Export selected PNGs as JPEG quality 95, 4:4:4, with a gallery')
    child.add_argument('--job', type=Path, required=True)
    child.add_argument('--output', type=Path, required=True)
    child.add_argument('--quality', type=int, default=95)
    child.set_defaults(run=export_jpeg)
    for command, function in [('add', add), ('select', select), ('build', lambda a: build(a.job.resolve(), read(a.job.resolve())))]:
        child = commands.add_parser(command)
        child.add_argument('--job', type=Path, required=True)
        child.set_defaults(run=function)
        if command == 'build':
            continue
        child.add_argument('--master', required=True)
        child.add_argument('--target', type=size_arg, required=True)
        if command == 'select':
            child.add_argument('--revision', type=int, required=True)
        else:
            child.add_argument('--image', type=Path, required=True)
            child.add_argument('--prompt-file', type=Path, required=True)
            child.add_argument('--note', default='')
    args = parser.parse_args()
    try:
        args.run(args)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'wallpapers: {error}\n')


if __name__ == '__main__':
    main()
