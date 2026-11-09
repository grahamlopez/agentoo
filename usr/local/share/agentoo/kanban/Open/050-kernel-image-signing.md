# Sign custom kernel images by default

Created: 2026-11-08
Status: Open — implementation complete; host acceptance pending

## Implemented

- `agentoo kernel install` requires signing regardless of firmware state.
  `--unsigned` explicitly installs the original image; `--yes` does not bypass
  signing. Config and build remain independent of signing inputs.
- Native `sbsign` and `sbverify --cert` use sbctl's standard file key and
  certificate at `/var/lib/sbctl/keys/db/db.{key,pem}`. Key creation and enrollment
  remain operator steps. No persistent signing switch or custom key loader.
- Missing tools fail with setup/unsigned guidance. After confirmation, privileged
  key/certificate readability checks run before mounting the ESP or staging
  system modules.
- Installation signs the disposable ESP copy in place, verifies it and restores
  mode `0644` before backing up or replacing either live artifact. Signing or
  verification errors retain staging paths, leave the old image/module pair
  unchanged and perform no firmware registration. Workspace hashes stay valid.
- Existing backup, replacement and registration behavior remains. No changes to
  kernel command-line merging, lockdown, modules or the Gentoo fallback machinery.
- `@kernel-dev` includes sbsigntools and sbctl. Help, parser-derived completion and
  kernel documentation cover the default and explicit bypass.
- The [initial setup guide](../../docs/secure-boot.md) covers signing an existing
  custom image separately, key backups, Gentoo/Windows trust, firmware editing
  modes, enrollment, boot verification and subsequent updates.

## Development validation

- All 40 kernel tests and 16 CLI tests passed, including the signed default,
  explicit unsigned installation without tools/keys, missing prerequisites,
  signing/verification failures, original workspace hashes, restrictive umask,
  matching backups and registration ordering.
- Real sbsigntools signed a temporary copy of an installed EFI kernel in place
  using a disposable certificate. Verification with the expected certificate
  succeeded; an unrelated certificate was rejected. No production keys, ESP
  files or firmware variables were changed.
- Full Python discovery ran 374 tests: 373 passed in the sandbox; the existing
  repository SSH-transport test failed because its temporary SSH-agent Unix
  socket could not bind. That isolated test passed when rerun with socket
  access. All six Lua regression scripts passed.
- Runbook shell syntax, local links and diff whitespace checks passed.

## Host acceptance still required

Follow the setup guide on the destination host. Record firmware model/version,
certificate fingerprints and these results before closing this card:

- Cold boot the signed custom image and independently managed Gentoo fallback
  with Secure Boot enabled; confirm Setup Mode disabled, selected release,
  encrypted-root unlock and normal startup.
- Boot Windows directly from its own drive; confirm Secure Boot enabled and
  normal BitLocker unlock after resuming protection if applicable.
- Install a subsequent custom build with the normal command and verify its
  signature. Confirm unsigned installation requires the explicit flag.

A signature check proves the image matches a certificate. Firmware acceptance
requires the actual boot tests; development checks do not establish it.
