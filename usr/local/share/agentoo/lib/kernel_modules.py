"""Rebuild installed NVIDIA drivers for one custom kernel using native Portage."""
from pathlib import Path


def package():
    try:
        import portage
    except ImportError as error:
        raise RuntimeError('Gentoo Portage Python support is required for NVIDIA module management') from error
    vardb = portage.db[portage.root]['vartree'].dbapi
    installed = vardb.match('x11-drivers/nvidia-drivers')
    if not installed:
        return None
    if len(installed) != 1:
        raise RuntimeError('resolve multiple installed NVIDIA driver versions before rebuilding modules')
    cpv = installed[0]
    settings = portage.config()
    settings.setcpv(cpv, mydb=vardb)
    if settings['EROOT'] != '/' or settings['PORTAGE_CONFIGROOT'] != '/':
        raise RuntimeError('NVIDIA module management supports only the local / Portage root')
    use = set(settings['PORTAGE_USE'].split())
    if 'modules' not in use:
        return None
    return dict(cpv=cpv, version=portage.versions.catpkgsplit(cpv)[2])


def rebuild(package, sources, output, release, modules_root, run):
    # Portage needs root access to retained outputs inside the private user home.
    run(['env', f'KERNEL_DIR={sources}', f'KBUILD_OUTPUT={output}',
         'FEATURES=-userpriv', 'emerge', '--oneshot', '--usepkg=n', '=' + package['cpv']], root=True)
    for name in ('nvidia', 'nvidia_modeset', 'nvidia_drm', 'nvidia_uvm'):
        def field(key):
            return run(['modinfo', '-b', modules_root.parent.parent, '-k', release, '-F', key, name], capture=True)
        if field('vermagic').split(' ', 1)[0] != release or field('version') != package['version']:
            raise RuntimeError(f'{name}: NVIDIA version or kernel release does not match the planned installation')
        path = Path(field('filename')).resolve()
        if not path.is_relative_to((modules_root / release).resolve()):
            raise RuntimeError(f'{name}: module resolved outside the target release: {path}')
