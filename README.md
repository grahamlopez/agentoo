# agentoo

An opinionated Gentoo distribution. See the
[project structure and configuration philosophy](usr/local/share/agentoo/docs/README.md)
and [development board](usr/local/share/agentoo/kanban/README.md).

Use `agentoo --help` for the unified system CLI. Commands include `agentoo git`,
`agentoo checkpoint`, `agentoo permissions check|fix`, and `agentoo secrets install`.
Help runs directly; all other operations announce and request
sudo authorization when invoked without root privileges. Git runs in root's
context. Secrets still confirm selected file replacements before Proton login.
The secrets implementation is kept in `usr/local/share/agentoo/commands/secrets`;
the entry point only handles command dispatch and elevation.
