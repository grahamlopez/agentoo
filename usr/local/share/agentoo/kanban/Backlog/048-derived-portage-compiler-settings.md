# Centralize derived Portage compiler settings after host selection

Created: 2026-10-31
Status: Backlog
Priority: Lower

[Common Portage policy](../../../../../../etc/portage/make.conf.d/00-common)
derives `CFLAGS`, `CXXFLAGS`, `FCFLAGS`, and `FFLAGS` from `COMMON_FLAGS`.
[Thinktop](../../../../../../etc/portage/make.conf.d/90-thinktop) and
[Flattop](../../../../../../etc/portage/make.conf.d/90-flattop) repeat all four
assignments after selecting their CPU-specific `COMMON_FLAGS`. Shell expansion
order currently makes the repetition necessary, but these derived assignments
represent the same policy.

Use the existing native sourcing order in
[make.conf](../../../../../../etc/portage/make.conf) to evaluate the shared
derivations once after the selected host has supplied its inputs. Keep host
fragments focused on actual differences. Check current consumers and override
semantics before moving assignments; do not add a generated configuration layer
or a custom host schema.

Preserve effective compiler values for every current target, including portable
generic/QEMU settings and host Rust flags. Matching values such as job counts or
build-storage choices do not automatically justify new shared host profiles;
leave those independent policies outside this bounded change.

Complete when each derived compiler assignment has one authoritative definition
and disposable configuration evaluation confirms unchanged effective values for
all current targets. Update relevant configuration guidance if ordering changes;
no package build or live configuration edit is needed for validation.
