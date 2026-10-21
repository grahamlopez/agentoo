"""Run with Kitty's Python to resolve its configuration and selected faces."""
import json
import os
from kitty.cli import default_config_paths
from kitty.config import load_config
from kitty.fonts.common import get_font_files

paths = list(default_config_paths(()))
extra = os.environ.get('AGENTOO_KITTY_EXTRA')
if extra:
    paths.append(extra)
bad = []
opts = load_config(*paths, accumulate_bad_lines=bad)
keys = ('font_family', 'bold_font', 'italic_font', 'bold_italic_font', 'font_size',
        'symbol_map', 'narrow_symbols', 'disable_ligatures', 'font_features',
        'modify_font', 'text_composition_strategy', 'box_drawing_scale')
settings = {key: str(getattr(opts, key)) for key in keys}
geometry = {}
for key in ('cell_width', 'cell_height'):
    mod = opts.modify_font.get(key)
    if mod:
        value = mod.mod_value
        suffix = {0: '', 1: '%', 2: 'px'}[int(value.unit)]
        geometry[key] = f'{value.val:g}{suffix}'
    else:
        geometry[key] = '0'
faces = {role: {key: str(face.get(key, '')) for key in
               ('family', 'style', 'path', 'postscript_name')}
         for role, face in get_font_files(opts).items()}
print(json.dumps({'paths': paths, 'settings': settings, 'geometry': geometry,
                  'faces': faces, 'errors': [str(line) for line in bad]}))
