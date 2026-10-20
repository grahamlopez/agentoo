"""Verify units, missing data, and discharge runtime calculations."""
import contextlib
import io
import json
from pathlib import Path
from unittest.mock import patch
import runpy
import tempfile
import unittest

module = runpy.run_path(str(Path(__file__).resolve().parents[3] / 'bin/agentoo-power'))
values = module['battery_values']


class PowerTest(unittest.TestCase):
    def check_values(self, fields):
        with tempfile.TemporaryDirectory() as directory:
            device = Path(directory)
            for name, value in fields.items():
                (device / name).write_text(str(value))
            return values(device)

    def test_energy_units(self):
        self.assertEqual(self.check_values(dict(status='Discharging', power_now=10000000,
            energy_now=40000000, energy_full=50000000, energy_full_design=62500000)), (10, 4, 80))

    def test_current_fallback(self):
        self.assertEqual(self.check_values(dict(status='Discharging', current_now=2000000,
            voltage_now=12000000, charge_now=6000000)), (24, 3, None))

    def test_charging_has_no_discharge_runtime(self):
        self.assertEqual(self.check_values(dict(status='Charging', power_now=10000000,
            energy_now=40000000)), (10, None, None))

    def test_missing_and_zero(self):
        self.assertEqual(self.check_values({}), (None, None, None))
        self.assertEqual(self.check_values(dict(status='Discharging', power_now=0,
            energy_now=40000000)), (0, None, None))

    def test_brief_format(self):
        with tempfile.TemporaryDirectory() as directory:
            device = Path(directory)
            fields = dict(capacity=97, status='Discharging', power_now=4800000,
                          energy_now=88480000)
            for name, value in fields.items():
                (device / name).write_text(str(value))
            self.assertEqual(module['brief'](device), '97% | 4.8 W | ~18h 26m')
            (device / 'status').write_text('Charging')
            self.assertEqual(module['brief'](device), '97% | 4.8 W | charging')
            for path in device.iterdir():
                path.unlink()
            self.assertEqual(module['brief'](device), 'unavailable | unavailable | unavailable')

    def test_json_partial_report_and_units(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            device = root / 'sys/class/power_supply/BAT0'
            device.mkdir(parents=True)
            for name, value in dict(type='Battery', status='Discharging',
                    capacity=50, power_now=10000000, energy_now=40000000).items():
                (device / name).write_text(str(value))
            output = io.StringIO()
            main = module['main']
            with patch.dict(main.__globals__, Path=lambda path: root / str(path).lstrip('/')):
                with patch('sys.argv', ['agentoo-power', '--json']), contextlib.redirect_stdout(output):
                    main()
            report = json.loads(output.getvalue())
            self.assertEqual(report['batteries'][0], dict(name='BAT0', status='Discharging',
                capacity_percent=50, power_watts=10, remaining_hours=4, health_percent=None))
            self.assertEqual(report['cpu_policies'], [])
            self.assertIsNone(report['platform_profile'])

    def test_abbreviated_options_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            module['build_parser']().parse_args(['--js'])
        self.assertEqual(error.exception.code, 2)
