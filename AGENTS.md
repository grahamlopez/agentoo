agentoo is an opinionated Gentoo distribution with agentic development and
system administration at its center.

As much as needed. As little as possible. Optimize for human understanding and
agent maintainability: few concepts, explicit behavior, and a small surface area.
These are design goals; existing complexity is not a precedent to copy.

Before adding a mechanism, check whether the project or an underlying tool
already provides it.

Configuration design

- Use application-native layers: shared defaults → selected host fragments →
  local user overrides, plus interactive state (`$XDG_STATE_HOME` / native
  store) only for live in-session preferences without rewriting authored config.
  Keep settings easy to find; avoid custom loaders and generated or copied
  configuration when native mechanisms suffice.
- Scope hardware exceptions narrowly to host fragments or hardware IDs without
  weakening shared defaults.
- Keep one authoritative definition of each setting or policy; reuse it rather
  than maintaining parallel representations.
- Keep agentoo opinionated; do not generalize for other distros. Only the small
  terminal-config subset listed in `usr/local/share/agentoo/installer/user-dots.sh`
  is exported—preserve its portability, and do not extend that pattern elsewhere.

Code design

- Every action should have a single source of truth, even if there are multiple
  user-facing activations via commands, configuration settings, shortcuts, and
  keybindings.
- Keep procedures direct and readable. Use helpers for repeated logic or coherent
  operations whose names make the caller easier to follow. Avoid trivial
  forwarding wrappers and abstractions for hypothetical needs.
- Add features, validation, and error handling for concrete requirements or failure
  risks, not speculative edge cases. Enforce safety and authority boundaries in
  code rather than prose, and preserve checks that prevent data loss or changes
  to the wrong target.
- Prefer a few consistent, composable mechanisms over special cases and new
  concepts. Prefer the simplest coherent solution over the smallest diff.
- Agentoo is pre-alpha; backward compatibility is not a requirement. Change
  interfaces directly and remove superseded code, aliases, and configuration.
  Update in-repository callers, tests, and documentation together; do not add
  compatibility layers or migration paths unless explicitly requested.
- Minimize Markdown and never mirror code or `--help` in docs. Route each kind
  of knowledge to its single operational home: tool flags/examples → CLI
  `--help`; config/code facts and *why-not* notes → comments at the site;
  package USE/setup/bump notes → Portage (`metadata.xml`, `README.gentoo`,
  ebuild comments); cross-tool mental models, multi-step human runbooks, and
  host baselines → `docs/`; deferred work, investigations, future designs,
  active checklists, and temporary fleet transitions → `kanban/`. Never keep
  verification logs, progress checkpoints, or `docs/history/`—Git is the archive.

See [philosophy, principles, and guides](usr/local/share/agentoo/docs/README.md)
for project details.
