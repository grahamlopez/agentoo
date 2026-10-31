agentoo is an opinionated Gentoo distribution with agentic development and
system administration at its center.

As much as needed. As little as possible. Optimize for human understanding and
agent maintainability: few concepts, explicit behavior, and a small surface area.
These are design goals; existing complexity is not a precedent to copy.

Before adding a mechanism, check whether the project or an underlying tool
already provides it.

Configuration design

- Use application-native layers: shared defaults → selected host fragments →
  local user overrides. Keep settings easy to find; avoid custom loaders and
  generated or copied configuration when native mechanisms suffice.
- Keep one authoritative definition of each setting or policy; reuse it rather
  than maintaining parallel representations.

Code design

- Keep code inline unless it is actually reused by multiple call sites. Extract
  small helpers from repetition, not anticipated reuse; avoid frameworks and
  abstractions for hypothetical needs.
- Make the supported path direct and readable. Add features, validation, and
  error handling for concrete requirements or failure risks, not speculative
  edge cases. Preserve checks that prevent data loss or changes to the wrong target.
- Prefer a few consistent, composable mechanisms over special cases and new
  concepts. Prefer the simplest coherent solution over the smallest diff.
- Agentoo is pre-alpha; backward compatibility is not a requirement. Change
  interfaces directly and remove superseded code, aliases, and configuration.
  Update in-repository callers, tests, and documentation together; do not add
  compatibility layers or migration paths unless explicitly requested.

See [configuration philosophy and guides](usr/local/share/agentoo/docs/README.md)
for project details.
