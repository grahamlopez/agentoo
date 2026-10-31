# Resolve the active kernel baseline recipe's authority and safety

Created: 2026-10-31
Status: Completed
Priority: Medium

[The historical baseline notes](../../docs/history/kernel-baseline-build.md) are linked from
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
the installer readability pilot in [card 030](../Backlog/030-installer-readable-procedures.md).

Complete when documentation links clearly distinguish historical evidence from
supported instructions, and active guidance does not invite reuse of another
machine's boot identity or bypass the supported installation safeguards.


## Completion, 2026-10-31

Moved the original baseline and Secure Boot experiments under `docs/history/`.
The archive explicitly identifies the machine UUIDs, old paths, direct writes
and Secure Boot commands as historical, unvalidated operating material. The
original experimental commands and unique signing/UKI/key-enrollment notes are
preserved; they were not promoted into a new maintained recipe.

The main documentation index links the supported kernel guide. That guide
states the separate signing/enrollment scope and links the historical Secure
Boot material with its status made explicit. The kernel development package-set
comment now points to current guidance; historical completed-card references
point to the archive and distinguish it from the supported workflow.

Verification: checked changed Markdown relative links and anchors, searched all
remaining baseline references, and confirmed the original experimental body is
preserved. No commands from the historical recipe were executed. The preceding
code change passed all 54 focused kernel/firmware tests; this card changes only
documentation and a package-set comment.
