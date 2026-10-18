#!/usr/bin/env python3
"""Report the power information exposed by the running kernel."""
import argparse
from pathlib import Path


def read(path):
    try:
        return path.read_text().strip() or None
    except OSError:
        return None


def number(path):
    try:
        return float(read(path))
    except (TypeError, ValueError):
        return None


def battery_values(device):
    def scaled(name):
        value = number(device / name)
        return value / 1_000_000 if value is not None else None

    watts = scaled('power_now')
    if watts is None:
        amps, volts = scaled('current_now'), scaled('voltage_now')
        if amps is not None and volts is not None:
            watts = amps * volts
    energy, full, design = (scaled(n) for n in ('energy_now', 'energy_full', 'energy_full_design'))
    charge, charge_full, charge_design = (scaled(n) for n in ('charge_now', 'charge_full', 'charge_full_design'))
    status = read(device / 'status')
    hours = None
    if status == 'Discharging':
        if energy is not None and watts:
            hours = energy / abs(watts)
        elif charge is not None and scaled('current_now'):
            hours = charge / abs(scaled('current_now'))
    health = full / design * 100 if full is not None and design else (
        charge_full / charge_design * 100 if charge_full is not None and charge_design else None)
    return watts, hours, health


def brief(device):
    watts, hours, _ = battery_values(device)
    capacity = read(device / 'capacity')
    charge = f'{capacity}%' if capacity else 'unavailable'
    rate = f'{abs(watts):.1f} W' if watts is not None else 'unavailable'
    if hours is not None:
        minutes = round(hours * 60)
        remaining = f'~{minutes // 60}h {minutes % 60:02d}m'
    else:
        status = read(device / 'status')
        remaining = status.lower() if status in ('Charging', 'Full', 'Not charging') else 'unavailable'
    return f'{charge} | {rate} | {remaining}'


def main():
    parser = argparse.ArgumentParser(prog='agentoo power', description=__doc__)
    parser.add_argument('action', nargs='?', choices=['show-all'],
                        help='show detailed battery and CPU power information (default: brief battery status)')
    args = parser.parse_args()
    supplies = Path('/sys/class/power_supply')
    batteries = []
    sources = []
    for device in sorted(supplies.glob('*')):
        if read(device / 'type') == 'Battery':
            if read(device / 'present') != '0':
                batteries.append(device)
        elif read(device / 'online') is not None:
            sources.append((device.name, read(device / 'online') == '1'))
    if args.action is None:
        if not batteries:
            print('Battery: unavailable')
        for device in batteries:
            prefix = f'{device.name}: ' if len(batteries) > 1 else ''
            print(prefix + brief(device))
        return
    online = [name for name, active in sources if active]
    source = ', '.join(online) if online else ('Battery' if any(read(b / 'status') == 'Discharging' for b in batteries) else 'Unavailable')
    print(f'Power source: {source}')
    if not batteries:
        print('Battery: unavailable')
    for device in batteries:
        watts, hours, health = battery_values(device)
        capacity = read(device / 'capacity')
        print(f'Battery {device.name}: {capacity + "%" if capacity else "unavailable"} · {read(device / "status") or "unknown"}')
        print(f'  Battery rate: {abs(watts):.1f} W' if watts is not None else '  Battery rate: unavailable')
        if hours is not None:
            minutes = round(hours * 60)
            print(f'  Time remaining: ~{minutes // 60}h {minutes % 60:02d}m')
        else:
            print('  Time remaining: unavailable')
        print(f'  Battery health: {health:.0f}% of design capacity' if health is not None else '  Battery health: unavailable')
    policies = sorted(Path('/sys/devices/system/cpu/cpufreq').glob('policy*'))
    for label, filename in [('CPU driver', 'scaling_driver'), ('CPU governor', 'scaling_governor'), ('Energy preference', 'energy_performance_preference')]:
        values = {}
        for policy in policies:
            value = read(policy / filename)
            if value:
                values.setdefault(value, []).append(policy.name)
        text = '; '.join(f'{value} ({", ".join(names)})' if len(values) > 1 else value for value, names in values.items())
        print(f'{label}: {text or "unavailable"}')
    print('Platform profile: ' + (read(Path('/sys/firmware/acpi/platform_profile')) or 'unavailable'))


if __name__ == '__main__':
    main()
