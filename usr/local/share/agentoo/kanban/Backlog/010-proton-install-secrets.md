# Explore Proton CLI access for installation secrets

Created: 2026-10-13
Status: Backlog

## Purpose

Explore optional Proton CLI access during installation to retrieve Wi-Fi
configuration secrets, SSH keys, and other explicitly selected provisioning
credentials. Keep the installer core small and retain manual setup when this
integration is unavailable or declined.

## Investigation

- Identify the appropriate Proton product/CLI, its supported secret types,
  authentication flow, installation requirements, and availability on a live host.
- Determine how the user selects the intended vault/items and associates them
  with a target host, without embedding personal identifiers in shared policy.
- Establish initial connectivity before remote secret retrieval: retrieving the
  first Wi-Fi password cannot depend on that same unconfigured Wi-Fi connection.
- Define how retrieved Wi-Fi credentials become native wpa_supplicant files and
  how SSH material reaches installer or post-boot account setup. Distinguish public
  login keys from private keys and decide whether private-key provisioning belongs
  in this workflow.
- Keep credentials out of Git, command arguments, logs, and installer output;
  define target file ownership/permissions and temporary authentication cleanup.
- Compare a small optional provisioning step with an installer integration.
  Preserve the standalone curl workflow, explicit user selection, and simple
  retry/defer behavior without making Proton an installation dependency.

## Completion criteria

Record supported workflows, required dependencies, connectivity/authentication
constraints, and a concrete recommendation. If worthwhile, demonstrate selected
Wi-Fi and SSH provisioning with disposable secrets, including failed retrieval,
retry, manual fallback, and removal of temporary session state. Record what is
retained on the target and covered by checkpoints.

This card authorizes investigation only; it does not enable account access or
change installer behavior.

Related: [007 installer and post-boot simplification](../Completed/007-installer-postboot-simplification.md).
