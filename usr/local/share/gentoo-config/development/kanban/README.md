# Development Kanban

This board records deferred project work. Move each card between `Backlog`,
`Open`, and `Completed` as its status changes; retain the context and add
implementation and validation notes when completing it.

This repository uses `/` as its work tree on managed installations. The board
therefore lives under `/usr/local/share/gentoo-config/development/kanban` as
passive development documentation, outside configuration fragments and executable
paths. No installer or configuration tool should consume cards as instructions
or apply them automatically. Tracking a card does not authorize its implementation.

Created on 2026-10-10. The immediate project focus is a Btrfs reset baseline for
the working QEMU install; the two initial cards are deliberately deferred work.
