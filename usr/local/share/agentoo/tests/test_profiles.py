"""Check native profile inheritance, package selection and local override layers."""
from pathlib import Path
import tempfile
import unittest

try:
    import portage
    from portage._sets.ProfilePackageSet import ProfilePackageSet
except ImportError:
    portage = None

ROOT = Path(__file__).resolve().parents[5]
OVERLAY = ROOT / 'usr/local/share/agentoo/portage'
GENTOO = Path('/var/db/repos/gentoo')
HOSTS = ('generic', 'qemu', 'flattop', 'startop', 'thinktop')


@unittest.skipUnless(portage and (GENTOO / 'profiles/default/linux/amd64/23.0/desktop/systemd').is_dir(),
                     'Portage and Gentoo AMD64 23.0 profiles required')
class ProfileTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='agentoo-profiles-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.config = self.root / 'etc/portage'
        (self.config / 'repos.conf').mkdir(parents=True)
        (self.config / 'repos.conf/test.conf').write_text(
            f'[DEFAULT]\nmain-repo = gentoo\n[gentoo]\nlocation = {GENTOO}\n'
            f'[agentoo]\nlocation = {OVERLAY}\n')
        (self.config / 'make.conf').write_text((ROOT / 'etc/portage/make.conf').read_text())

    def settings(self, host):
        selected = self.config / 'make.profile'
        selected.unlink(missing_ok=True)
        selected.symlink_to(OVERLAY / 'profiles/hosts' / host)
        return portage.config(config_root=str(self.root), target_root=str(self.root), env={})

    def test_hardware_packages_follow_profile_without_environment_sets(self):
        laptop = {'media-libs/libva-intel-media-driver', 'media-video/libva-utils', 'sys-power/acpilight'}
        for host in HOSTS:
            settings = self.settings(host)
            packages = {str(atom) for atom in ProfilePackageSet(settings._locations_manager.profiles_complex).getAtoms()}
            expected = set() if host in ('generic', 'qemu') else laptop.copy()
            if host == 'thinktop':
                expected.add('sys-firmware/sof-firmware')
            with self.subTest(host=host):
                self.assertEqual(packages, expected)
                self.assertFalse((self.root / 'var/lib/portage/world_sets').exists())

    def test_graphics_and_firmware_defaults_remain_host_specific(self):
        for host in HOSTS:
            settings = self.settings(host)
            with self.subTest(host=host):
                self.assertEqual(settings['ARCH'], 'amd64')
                self.assertEqual(settings['ABI'], 'amd64')
                if host not in ('generic', 'qemu'):
                    self.assertEqual(settings['VIDEO_CARDS'], 'intel')
                    cpu = 'raptorlake' if host == 'flattop' else 'arrowlake'
                    self.assertEqual(settings['CFLAGS'], f'-march={cpu} -O2 -pipe')
                else:
                    self.assertEqual(settings['CFLAGS'], '-O2 -pipe')
                settings.setcpv('sys-kernel/linux-firmware-20260622')
                self.assertEqual('savedconfig' in settings['USE'].split(), host not in ('generic', 'qemu'))
                self.assertFalse({'compress-xz', 'compress-zstd', 'deduplicate'} & set(settings['USE'].split()))

    def test_native_local_settings_override_profile_defaults(self):
        with (self.config / 'make.conf').open('a') as file:
            file.write('COMMON_FLAGS="-O1 -pipe"\nCFLAGS="-Os"\nVIDEO_CARDS="amdgpu"\n')
        (self.config / 'package.use').mkdir()
        (self.config / 'package.use/local').write_text('sys-kernel/linux-firmware -savedconfig\n')
        settings = self.settings('thinktop')
        self.assertEqual(settings['CFLAGS'], '-Os')
        self.assertEqual(settings['COMMON_FLAGS'], '-O1 -pipe')
        self.assertEqual(settings['VIDEO_CARDS'], 'amdgpu')
        settings.setcpv('sys-kernel/linux-firmware-20260622')
        self.assertNotIn('savedconfig', settings['USE'].split())


if __name__ == '__main__':
    unittest.main()
