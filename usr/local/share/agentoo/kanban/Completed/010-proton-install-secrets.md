# Explore Proton CLI access for installation secrets

Created: 2026-10-13
Status: Completed
Completed: 2026-10-13

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

## Implementation and decisions

The user subsequently authorized a versioned binary ebuild, a simple terminal
provisioning script, and a tracked QEMU profile. Installer behavior and package
sets remain unchanged. Explicit profile selection is preferred over automatic
host discovery. The QEMU profile intentionally contains the user's chosen vault
item names and repository mapping, but no secret values.

- Minimal local overlay packages official Proton Pass CLI 2.4.2 binaries for
  amd64/arm64. Portage manages installation, updates, and removal. Both upstream
  SHA-256 hashes and ELF dependencies were inspected; amd64 ran locally.
  Gentoo installation was subsequently confirmed by the user in QEMU.
- `agentoo-secrets` runs after account creation and network setup. It prompts
  once for selected destinations, then invokes `pass-cli login --interactive`.
  The user's password/TOTP flow works without a browser. Proton's FIDO/U2F
  login currently requires a browser; standalone YubiKey login is not promised.
- Each invocation uses filesystem key storage in a private `/run` directory.
  Exit cleanup logs out and deletes temporary session state. No SSH agent or
  other persistent daemon is started. Normal failure/interruption runs cleanup;
  SIGKILL cannot. Reboot clears `/run`.
- Selected files are replaced with mode 0600, owned by root or the chosen user.
  SSH private/public client keys are provisioned, not inbound authorized keys.
  Wi-Fi is a complete native configuration stored as a secure note. Template
  injection is supported, with format escaping left to the template author.
- GitHub provisioning writes a root-owned plaintext credential and configures
  the installed repository's HTTPS push URL and built-in credential store.
  The user explicitly deferred per-push PIN/unlock handling and accepted this.
- Existing installer Wi-Fi copy/prompt/defer paths remain the manual fallback.
  Remote retrieval requires pre-existing connectivity; it cannot obtain the
  password needed to establish that same initial connection.
- Credentials remain outside Git but are retained in local checkpoints on the
  encrypted drive. This retention was explicitly accepted. Temporary Proton
  session state is not intended to be retained on disk.
- Pi API-token configuration, additional host profiles, physical Wi-Fi service
  testing, and per-push unlocking are future work outside this initial scope.

## Validation (2026-10-13)

- Mock CLI checks passed for category selection, spaced field names, direct
  retrieval, template rendering, mode 0600, failed retrieval preserving an
  existing destination, and cleanup on success/failure.
- Real Git against dummy credentials selected the token for the agentoo HTTPS
  repository, but not another repository. No remote push was performed locally.
- The user confirmed a complete real QEMU `all` run installed GitHub credentials,
  both SSH key files, and the wlan0 configuration. The user confirmed GitHub
  authentication, Wi-Fi file contents, and temporary-directory cleanup.
- The user confirmed the public key derived from the installed private key
  matches the installed public key. The wlan0 entry is a file-installation test;
  QEMU uses Ethernet. Real vault data was used by the user; local automated
  checks used dummy values rather than accessing the user's account.
- Overlay traversal initially failed because Git created directories as 0700.
  Explicit directory permission policy fixed this. Generated Python bytecode
  was removed from tracking and excluded.

## Final acceptance (2026-10-13)

The user verified the remaining cases in the QEMU VM:

- Answering `n` exited before Proton login or installation.
- A nonexistent vault item produced a retrieval error, installed no destination,
  and left no `/run/agentoo-secrets.*` directory.
- Correcting the reference and rerunning succeeded; the resulting public key
  matched the previously installed key, and temporary session cleanup succeeded.
- Test profile and destination were removed afterward.

The initial investigation and three-case post-install provisioning scope are
complete. Manual fallback remains the independent installer/account tools;
provisioning failure does not block their use. Deferred work listed above does
not block this card's completion.

Related: [007 installer and post-boot simplification](../Completed/007-installer-postboot-simplification.md).
