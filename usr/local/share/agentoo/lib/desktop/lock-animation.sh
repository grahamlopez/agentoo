#!/bin/sh
# Visuals only: the parent Wayland locker owns authentication and input.
# Stop on animation failure; never drop into an interactive shell.
set -e
while :; do
    ttfx --frame-rate 30 --anchor-canvas c --anchor-text c decrypt <<'TEXT'
a g e n t o o

Session locked
TEXT
    sleep 1
done
