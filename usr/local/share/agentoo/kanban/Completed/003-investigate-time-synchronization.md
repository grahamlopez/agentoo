# Clarify time readiness in early-boot diagnostics

Created: 2026-10-11
Status: Completed

After restoring the QEMU fresh-install checkpoint, the guest booted successfully
and its diagnostic helper reported zero failed checks. At approximately 31
seconds after boot, however, timedatectl reported an active NTP service but
`System clock synchronized: no`; timesync-status showed `Server: n/a`, packet
count zero, and `1.gentoo.pool.ntp.org`. Networking, DNS, and HTTPS checks passed.
This observation does not yet establish a persistent synchronization failure.

Investigate whether synchronization completes after a reasonable wait. Capture
`timedatectl status`, `timedatectl timesync-status`, and
`journalctl -b -u systemd-timesyncd`; inspect configured servers, name resolution,
and NTP reachability if it remains unsynchronized. Compare ordinary and restored
boots before attributing the behavior to checkpoint restoration.

The combined first-boot script reports time state in `--verify-only` mode
without requiring synchronization; checkpoint mode requires synchronized time.
Decide whether diagnostics should wait briefly or report this distinction more
clearly. Keep output concise and avoid treating normal startup delay as failure.

Complete when the observed behavior is explained, any needed change is verified
on QEMU, and both modes communicate time readiness consistently.

## Follow-up evidence — 2026-10-11

Later in the same restored boot, `NTPSynchronized=yes`. The consolidated
script passed live `--verify-only` diagnostics and default checkpoint preflight;
the user-confirmation plan was reached and creation was declined. No time-service
configuration changes were needed. There is no evidence of a persistent NTP
failure or a restore-induced defect.

Remaining scope: decide whether verify-only output should explicitly distinguish
successful diagnostic commands from synchronized time, rather than suggesting
checkpoint readiness through its zero-failed-checks summary. Investigate NTP
configuration or reachability only if a persistent failure is observed again.

## Fresh-install evidence and output refinement — 2026-10-11

On the fresh installation's first boot, diagnostic commands completed with zero
failed checks, but checkpoint preflight found `NTPSynchronized=no` and raised an
uncaught `RuntimeError`. No checkpoint was created. This reproduces the readiness
difference without restoration; it does not establish a persistent NTP failure.

- Successful diagnostics now distinguish checkpoint preflight from verify-only
  mode, where synchronized time is not required.
- Expected preflight failures print `Checkpoint not created:` and exit nonzero
  without a traceback. Unsynchronized time advises waiting and rerunning.
- Unexpected errors retain their tracebacks. No wait loop or retry machinery was
  added, and the synchronized-time requirement remains unchanged.

Validation: isolated execution of the actual Python preflight covers synchronized
and unsynchronized time, another expected prerequisite failure, and an unexpected
error. Shell diagnostic summaries are checked in both modes.

## Fresh-guest verification — 2026-10-11

- The user reran firstboot successfully after synchronization and created a
  checkpoint; no persistent NTP failure was observed.
- After real default restoration on the fresh guest, `NTPSynchronized=yes` and
  normal firstboot diagnostics passed.
- The revised script ran from disposable `/run` files: verify-only printed its
  readiness distinction, and the real checkpoint preflight passed.
- Repeating that preflight with only the time query forced to `no` exited nonzero
  with the concise wait-and-rerun message and no traceback. No capture ran.

The startup delay and diagnostic/readiness distinction are now explained and
verified. Reopen investigation only if synchronization persistently fails.
