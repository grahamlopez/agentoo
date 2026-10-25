# Make first-boot verification output usable on a console

Created: 2026-10-25
Status: Backlog

`/root/001-firstboot-verify-and-checkpoint.sh` is normally run from a console
where scrollback is difficult. Later checks obscure earlier results and recovery
instructions, making failures and warnings hard to review.

Provide a concise final summary of passed/failed checks and warnings, with
recovery guidance for items needing attention. Consider saving detailed output
to a root-only report and offering a pager for review. Keep hardware information
separate from required checks in the presentation, and preserve existing
verification and checkpoint behavior, including `--verify-only`.

Validate on a TTY with enough output to exceed one screen and with failures in
early checks: the user should be able to identify every unresolved issue and
retrieve its details without relying on terminal scrollback.
