# Reduce kernel code using test and usage evidence

Created: 2026-10-14
Status: Backlog

## Objective and prerequisites

Minimize kernel size, code surface and boot time while preserving required
features and performance. Begin deliberate reduction after acceptance of the
relevant [single-binary functional baseline](../Completed/014-single-binary-kernel-baseline.md).
Use the [shared configuration workflow](../Open/015-shared-kernel-configuration-workflow.md)
to record and reproduce changes across hosts.

Maintain one shared driver/capability configuration supporting all Agentoo hosts,
with host-specific boot parameters, firmware and microcode embedded in each
host's binary. A code reduction must preserve the union of host requirements;
a driver unused on one host may be essential on another. Distinguish shared code
removal from changes to a particular host's embedded payload.

Nouveau exclusion and changes necessary for single-binary/built-in operation
belong to the initial baseline. Do not present them as experimentally validated
reduction results.

## Investigation and working approach

- Change one subsystem or coherent group at a time. Identify affected
  requirements and a restoration path before testing.
- Record the exact configuration delta, rationale, source version, host/device
  scope and artifact identity, together with tests and observations.
- Compare functionality and workload performance as well as EFI file size,
  kernel code/data size, boot timing, power behavior and memory where relevant.
  Distinguish firmware/initramfs size from kernel code and human unlock time
  from boot processing.
- Accumulate ordinary-use observations, including the scenarios actually
  exercised, dates, boots and suspend/resume cycles. Elapsed time without a
  failure does not establish coverage of an unused feature.
- Keep unsuccessful experiments and regressions so later hosts and upgrades
  benefit from the findings. Restore required functionality and revise the
  applicable conclusion when a regression appears.
- Keep evidence scoped to the hosts, workloads and versions tested. Consider
  applicability when reusing a removal on another host or kernel version.
- During capture review, the user chooses changes to the shared configuration.
  Review each removal against all hosts' recorded requirements and identify
  untested hosts explicitly. No shared/host placement or promotion process is
  required.

## Completion criteria

Agree concrete reduction candidates and acceptance tests from the functional
baseline. Demonstrate a repeatable reduction-and-restoration cycle, with durable
evidence explaining both the benefits and limits of each accepted change. Refine
long-term observation criteria through use rather than prescribing an elaborate
process before the first candidate exists.
