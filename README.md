# agentoo

An opinionated Gentoo distribution with agentic development and system
administration at its center. This repository brings its configuration and
installer under one roof, with a local overlay for custom ebuilds.

Right now, this is built from the following main components:

1. An installer that makes very specific decisions about installing for
   previously onboarded target hosts.
2. A configuration repository that mirrors the target filesystem. A bare repo
   is checked out using `/` as its working directory
3. A suite of CLI tools (`agentoo --help`; conventions in
   [lib/cli.py](usr/local/share/agentoo/lib/cli.py)) to aid in configuration
   and management
4. A portage overlay with custom ebuilds

**Opinionated** means that only very specific configurations are supported and
that many preferences are hardcoded for simplicity over user-choice
flexibility. Support is hardware and use-case specific, so for a new host
configuration, use the [target host configuration checklist](usr/local/share/agentoo/docs/host-onboarding.md).

Find [philosophy, principles, and guides](usr/local/share/agentoo/docs/README.md)

A [kanban development board](usr/local/share/agentoo/kanban/README.md) is
haphazardly maintained for capturing deferred and ongoing work.
