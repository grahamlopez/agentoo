# Secrets provisioning and trust model

Run `agentoo secrets install --help` for CLI usage, options, and examples, and
see [profile.example](profile.example) for row syntax and all four methods
(`field`, `uuid`, `template`, `github`). This note covers only the trust model
and security boundaries.

## Trust and Git boundaries

- **Trusted inputs:** Profiles and destination paths are trusted administrator
  inputs; `agentoo secrets` is deliberately not a general hardened deployment
  engine. Profiles are plain data, not executable shell configuration, and are
  always selected explicitly by path (never inferred from the host profile).
- **Secrets stay out of Git:** Provisioned credentials and local profiles under
  `/etc/agentoo/secrets/` are excluded by `/etc/agentoo/gitignore`. Only
  reference-only host profiles are explicitly un-ignored—never put secret values
  in a tracked profile.

## Authentication and session isolation

- **Interactive login only:** Actual installation always requires an interactive
  terminal for Proton Pass `login --interactive` (password + TOTP). `--no-input`
  supports `--dry-run` only; `--yes` skips file-replacement confirmation but
  never bypasses authentication.
- **Ephemeral `/run` session:** Each invocation creates a private memory-backed
  directory under `/run` with the CLI filesystem key provider (leaving any
  ordinary `pass-cli` session untouched) and logs out and deletes the directory
  on exit, error, or cancellation. SIGKILL or power loss skips cleanup; `/run`
  clears on reboot.
- **Redacted diagnostics:** Captured provider errors and secret values are never
  printed in diagnostics. Avoid shell tracing when running installs.

## Replacement and `github` method semantics

- **Overwrite only:** Selected files are overwritten at mode `0600` (no append
  or merge); existing parent directories keep their ownership and permissions.
  Partial installs can occur if a later fetch or write fails—fix the failing
  reference and rerun.
- **`github` method:** Writes a root-owned `0600` plaintext credential file at
  `/var/lib/agentoo/secrets/github.credentials` and sets an HTTPS push URL for
  `/var/lib/agentoo/repository.git` without changing its fetch URL (see the
  unlocked-console trust zone in [docs/README.md](../docs/README.md#security-and-convenience-boundaries)).
