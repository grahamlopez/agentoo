# Resolve the active kernel baseline recipe's authority and safety

Created: 2026-10-31
Status: Backlog
Priority: Medium

[The manual baseline notes](../../docs/kernel-baseline-build.md) are linked from
the main documentation index without a historical designation. They contain
literal machine filesystem/LUKS UUIDs, ambiguous working-directory assumptions,
source Makefile editing, and direct installation into system modules. Their
procedure differs from the reviewed `agentoo kernel` workflow's specialization,
staging, and validation.

Decide whether this document is historical evidence or maintained operating
guidance. Archive and label the historical experiment, or reconcile a maintained
procedure with the supported implementation and local identity inputs. Preserve
useful material that has no replacement, including the separately scoped Secure
Boot notes; do not discard the entire document without that review.

Keep manual reproducibility as a project goal. Avoid maintaining a second
executable-looking recipe for the same procedure when the implementation can
serve as its readable reference. This card concerns kernel documentation, not
the installer readability pilot in [card 030](030-installer-readable-procedures.md).

Complete when documentation links clearly distinguish historical evidence from
supported instructions, and active guidance does not invite reuse of another
machine's boot identity or bypass the supported installation safeguards.
