# Build a self contained Agentoo kernel

Build one shared driver and capability configuration for all Agentoo hosts.

- host-specific boot parameters, firmware and CPU microcode are embedded into
  each host's self-contained EFI binary
- all selected kernel code is built in
- modules and nouveau are disabled
- the working distribution kernel is retained as recovery

This runbook grows as the manual procedure is exercised. Prerequisite package
resolution has been reviewed on Thinktop; installation, configuration, build and
boot have not yet been verified. The operator runs host commands and reports
results before proceeding to the next step.

Progress and open investigations belong in the
[baseline card](../kanban/Open/014-single-binary-kernel-baseline.md).

The [configuration workflow card](../kanban/Open/015-shared-kernel-configuration-workflow.md)
tracks automation developed from the demonstrated manual procedure.

## Install sources and core inspection tools

The repository's `@kernel-dev` set contains sources plus PCI, USB, platform and
sensor inspection tools:

```sh
sudo emerge -avn @kernel-dev
```

## Subsequent steps

Document commands and verified results as each stage is performed:

1. Collect hardware, firmware and boot inputs while preserving the existing
   fallback and keeping raw machine identifiers outside Git.
2. Prepare a separate build directory for the explicitly selected source tree;
   retain its source/patch provenance and original `make defconfig` output.
3. Run `make mod2yesconfig`, disable module support and nouveau, add required
   functionality, and review dependency resolution for lost features.
4. Prepare the target's embedded boot parameters, firmware, early microcode and
   initramfs; retain the exact inputs and resulting configuration.
5. Build, validate, install a separately named candidate, and coordinate a test
   boot while retaining the distribution fallback.
6. Record single-binary boot success separately from feature and performance
   acceptance before deliberate code reduction.

