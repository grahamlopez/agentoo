"""Check native NVIDIA targeting and wrong-version/wrong-target rejection."""
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))
import kernel_modules


class ModulePackageTests(unittest.TestCase):
    def test_package_uses_native_installed_version_and_requires_local_root(self):
        class Settings(dict):
            def setcpv(self, *args, **kwargs):
                pass
        settings = Settings(EROOT='/', PORTAGE_CONFIGROOT='/', PORTAGE_USE='modules')
        cpv = 'x11-drivers/nvidia-drivers-595.104.02-r1'
        tree = SimpleNamespace(dbapi=SimpleNamespace(match=lambda atom: [cpv]))
        portage = SimpleNamespace(root='/', db={'/': {'vartree': tree}},
                                  config=lambda: settings,
                                  versions=SimpleNamespace(catpkgsplit=lambda value: ('x11-drivers', 'nvidia-drivers', '595.104.02', 'r1')))
        with patch.dict(sys.modules, portage=portage):
            self.assertEqual(kernel_modules.package(), dict(cpv=cpv, version='595.104.02'))
            settings['PORTAGE_USE'] = ''
            self.assertIsNone(kernel_modules.package())
            settings['EROOT'] = '/different-root/'
            with self.assertRaisesRegex(RuntimeError, 'local / Portage root'):
                kernel_modules.package()

    def test_rebuild_checks_release_version_and_installed_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'lib/modules'
            fields = dict(vermagic='release SMP', version='1', filename=str(root / 'release/video/nvidia.ko'))
            calls = []
            def run(args, **kwargs):
                calls.append((args, kwargs))
                if args[0] == 'modinfo':
                    return fields[args[args.index('-F') + 1]]
                self.assertEqual(args, ['env', 'KERNEL_DIR=/source', 'KBUILD_OUTPUT=/output',
                                       'FEATURES=-userpriv', 'emerge', '--oneshot', '--usepkg=n',
                                       '=x11-drivers/nvidia-drivers-1'])
                self.assertEqual(kwargs, {'root': True})
            package = dict(cpv='x11-drivers/nvidia-drivers-1', version='1')
            kernel_modules.rebuild(package, Path('/source'), Path('/output'), 'release', root, run)
            self.assertEqual(sum(args[0] == 'modinfo' for args, _ in calls), 12)
            for key, bad, message in [('vermagic', 'other-release SMP', 'version or kernel release'),
                                      ('version', '2', 'version or kernel release'),
                                      ('filename', str(root / 'other-release/nvidia.ko'), 'outside the target release')]:
                original = fields[key]
                fields[key] = bad
                with self.subTest(field=key), self.assertRaisesRegex(RuntimeError, message):
                    kernel_modules.rebuild(package, Path('/source'), Path('/output'), 'release', root, run)
                fields[key] = original


if __name__ == '__main__':
    unittest.main()
