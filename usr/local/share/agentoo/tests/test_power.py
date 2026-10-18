"""Verify units, missing data, and discharge runtime calculations."""
from pathlib import Path
import runpy
import tempfile
import unittest

values = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'commands/power.py'))['battery_values']


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
