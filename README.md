# agentoo

An opinionated Gentoo distribution. See the
[project structure and configuration philosophy](usr/local/share/agentoo/docs/README.md)
and [development board](usr/local/share/agentoo/kanban/README.md).

Use `agentoo --help` for the unified CLI: Git, checkpoints, managed permissions,
secrets, display backlight, screenshots, and power status.
Operations request sudo only when needed; help and desktop utilities run as the
current user. Arbitrary Git commands also run as the current user: use explicit
`sudo agentoo git ...` for protected system repository writes. Git may require
root even for reads that traverse protected files or access its database.
Secrets confirm selected file replacements before Proton login.

`agentoo power` prints a brief status such as `97% -- 4.8 W -- ~18h 26m`.
Charging/full batteries show their status in place of discharge runtime.
Multiple batteries get a labeled line each.

`agentoo power show-all` reports each battery's charge, charging/discharging wattage,
estimated discharge runtime, and health, plus CPU governor, energy preference,
and platform profile where available. Battery wattage is not wall power;
unavailable kernel measurements are labeled explicitly.

The old `agentoo-backlight` and `agentoo-screenshot` names remain compatibility
wrappers. Screenshot files go to `~/Downloads/Screenshots`.
