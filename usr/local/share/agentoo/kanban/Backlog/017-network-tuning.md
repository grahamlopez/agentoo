# Investigate network tuning

Created: 2026-10-15
Status: Backlog

## Scope

Treat network tuning as a separate effort from establishing the shared kernel
configuration and single-binary boot. Introduce `ethtool`, `iw` and other tools
when a concrete network investigation needs them, rather than including them in
the initial `@kernel-dev` prerequisites.

Establish workloads and measurements before changing settings. Investigate link
capabilities, offloads, queues, wireless behavior and related performance controls
as relevant to those workloads. Record the conditions, measurements, changes and
restoration procedure.

Required network drivers, firmware, VPN protocols and virtualization networking
features remain within [kernel functional acceptance](../Open/014-single-binary-kernel-baseline.md).
Separating tuning does not remove these requirements from the shared kernel.
