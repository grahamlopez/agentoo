# Installer and post-boot simplification

Created: 2026-10-12
Status: Open
Source: [Agentoo installer and post boot audit](https://chatgpt.com/space/page_cc2bd4729cd08191807d5b06b4ca0b99)
Initial audit baseline: `7c08b29`
Repository baseline when opened: `00fe99e`

## Record and maintenance

The audit and agreed decisions below preserve the current Page content in full. Keep this rationale as the historical record. Append implementation progress, validation evidence, and later decisions in the sections after the preserved document; reference the existing A, D, P, S, R, and T identifiers. If a decision changes, record the new rationale and its relationship to the original rather than silently rewriting the original.

This card records the implementation plan. Its creation does not mean any implementation or deployment has been completed. Keep optional and deferred work distinguished from required actions.

## Preserved audit and decisions

The strongest simplification would be to **narrow the supported contract**, then remove the machinery needed to support alternatives. The project already assumes a fairly specific system; the installer exposes more flexibility than the post-boot tools actually support.

The audit covers the installer, both post-boot scripts, checkpoint implementation, permission helper, Git hooks, and deployed configuration. The findings below describe the implementation reviewed; the decisions incorporate the subsequent discussion. Shell and embedded Python syntax checks passed during the source audit. The changes and validation in the action list remain to be implemented; no installer or deployed configuration changes have been made as part of this review.

Stable references: **A01–A06** identify the priority findings, **D01–D17** the departures from defaults, **P01–P05** the Python observations, **S01–S11** the other simplifications, and **R01–R07** the revised implementation sequence. **T01–T12** identify the concrete actions below. Existing references and comment threads remain part of the review.

## Findings I would address first

### A01 The installer supports layouts that checkpointing cannot handle

`--root-subvol` and `--home-subvol` allow custom names, while the [checkpoint implementation](/home/graham/Projects/agentoo/boot/agentoo/checkpoint.sh:129) explicitly requires `@` and `@home`. First-boot verification accepts other names, only for checkpoint creation to reject them afterward.

There are also inconsistent character restrictions: initial argument validation accepts `+`, while later kernel and first-boot validation reject it.

**Agreed decision:** fix the minimal layout to `@` and `@home` and remove the custom subvolume-name options. This eliminates configuration propagation and validation while making installation and recovery agree. Retain ESP capture and restoration: checksum-verified EFI archives, restoration that preserves later EFI additions, unchanged firmware entries, and the recovery script on the ESP outside `EFI/`.

### A02 Deferred Wi-Fi is treated as a failed installation

The installer permits deferring Wi-Fi, but [first-boot diagnostics](/home/graham/Projects/agentoo/root/001-firstboot-verify-and-checkpoint.sh:34) require an active supplicant for every detected wireless interface. A machine using working Ethernet with deliberately unconfigured Wi-Fi therefore fails verification and never reaches the checkpoint prompt.

**Agreed decision:** require supplicant health only for interfaces actually configured/enabled for Wi-Fi. Treat other wireless interfaces as informational. Add an explicit configure/defer choice for physical targets. Today the installer imports saved profiles first and prompts for an SSID only when no supported profiles are found; a blank SSID defers Wi-Fi. QEMU skips Wi-Fi. A desktop without a wireless interface does not trigger this failure, but an Ethernet-connected desktop with unconfigured wireless hardware can.

### A03 Wi-Fi setup still assumes the installation machine is the destination

The [installer](/home/graham/Projects/agentoo/usr/local/share/agentoo/installer/gentoo-install.sh:2607) discovers interfaces in the host’s `/sys/class/net`, creates configurations for those names, and enables those service instances in the target.

Custom device renaming is gone, but installing a physical disk from another machine can still configure the wrong interface. CPU flags and automatic microcode selection similarly use the installation host, although those have explicit overrides.

**Agreed decision:** physical installations run on the destination hardware for now. Host interface discovery and CPU detection are appropriate within that scope; document it instead of adding cross-machine interface-selection machinery. QEMU/NBD remains a separate supported workflow with explicit host-versus-guest assumptions.

### A04 The recorded kernel version becomes stale after normal kernel updates

[`gentoo-dist.version`](/home/graham/Projects/agentoo/usr/local/share/agentoo/installer/gentoo-install.sh:2163) is written by the installer. The installed kernel hook checks the ESP but does not update that record. [First-boot preflight](/home/graham/Projects/agentoo/root/001-firstboot-verify-and-checkpoint.sh:104) later compares the running kernel against the original version and recommends rebooting when they differ.

After booting a newer kernel, rebooting will not resolve that mismatch.

**Agreed decision:** keep the version record only as installation handoff data, where it identifies the release used for initial boot guidance. Remove its permanent equality check from reusable verification; do not add an update hook solely to maintain the record. Verify the maintained distribution fallback's modules and matching EFI kernel/initramfs independently of the running kernel. A future custom kernel may intentionally be running while the distribution fallback remains available. Checkpoint creation does not need this version record.

### A05 Kernel policy is broader than its fallback description suggests

The [kernel phase](/home/graham/Projects/agentoo/usr/local/share/agentoo/installer/gentoo-install.sh:2073) writes persistent policy including:

- Global `dist-kernel`.

- Global Dracut configuration disabling host-only generation and forcing drivers.

- Systemd kernel-install integration and a selected boot layout.

- Stable keyword overrides that counteract testing keywords in the tracked common configuration.

- Firmware policy that counteracts `savedconfig` in the tracked common configuration.

These affect later package and kernel operations, beyond preparing one fallback kernel. A source distribution kernel installed through Portage can use the same policy. A separately built image explicitly copied with its own embedded initrd can remain independent by bypassing that pipeline. The concern is hidden coupling and contradictory policy; merely having a custom image does not cause the current settings to overwrite it.

**Agreed decision:** stable `gentoo-kernel-bin` remains the independently maintained, vanilla fallback. Use Gentoo's packaged module/initramfs/kernel installation tools and one tracked source of policy. Remove common settings that immediately need opposing overrides, including firmware `savedconfig` and distribution-kernel testing keywords. Physical firmware boot registration remains manual. Retain the installer's existing offline registration in an explicitly selected QEMU variable store so development guests are easy to create. The future custom-image path is not yet defined and must use distinct artifacts without changing the fallback pipeline, its files, or its configuration.

### A06 QEMU inherits a build storage optimization that is unsuitable as a minimal default

The [QEMU fragment](/home/graham/Projects/agentoo/etc/portage/make.conf.d/90-qemu:4) redirects builds to `/dev/shm`. The printed VM command allocates 4 GiB of RAM; builds then compete with the running system for memory and tmpfs space.

Gentoo’s standard build location is `/var/tmp`; its own configuration example notes that build storage can become very large. [Portage configuration example](https://github.com/gentoo/portage/blob/master/cnf/make.conf.example)

**Agreed decision:** retain optional host-backed `/dev/shm` builds during installation, but make that choice temporary for QEMU. After boot, the guest inherits normal disk-backed Portage build storage. Thinktop/Startop may retain deliberate physical-host RAM-build policy. The host's tmpfs capacity and available memory still constrain installation builds; no elaborate memory-management mechanism is required.

## Departures from Gentoo or packaged defaults

Gentoo does not prescribe one universal networking, filesystem, or boot setup. Choosing a documented component is different from overriding its packaged behavior. The table preserves the implementation observed in the audit and records the agreed disposition; desired changes are not claims about changes already implemented.

| Reference | Area | Current Agentoo behavior | Agreed disposition |
|---|---|---|---|
| D01 | Base system | AMD64 desktop/systemd stage3 | Retain the deliberate installation scope. |
| D02 | Storage | GPT, 1 GiB ESP at `/boot`, LUKS2, Btrfs, separate `@`/`@home` | Retain the architecture and fix the subvolume names; preserve ESP checkpoint/restore. |
| D03 | Mount options | `noatime`, `compress=zstd:1`, ESP `umask=0077` | Retain as explicit storage policy. |
| D04 | Networking | dhcpcd plus packaged per-interface wpa_supplicant | Retain; physical installation runs on the destination hardware. |
| D05 | DHCP configuration | Separate `gentoo-install.conf` and replacement service `ExecStart` | Use the packaged service and normal `/etc/dhcpcd.conf` with only necessary settings. |
| D06 | DNS | Force dhcpcd to bypass resolvconf using a nonexistent executable path | Keep direct dhcpcd DNS ownership; remove the workaround after verifying the systemd shim and provider configuration. |
| D07 | Services | Enable-only presets, then disable competing network, logging, and time services | Keep the chosen network/time architecture; use packaged journald defaults and avoid additional DNS services. |
| D08 | Logging | Persistent journal, 256 MiB maximum, 512 MiB kept free | Remove the entire Agentoo journald drop-in and inherit packaged logging defaults; preserve existing logs. |
| D09 | Maintenance | Custom monthly Btrfs scrub service/timer | Retain the small, explicit maintenance addition. |
| D10 | Systemd storage | Ordinary directories replace vendor subvolumes; image/container services masked; import behavior overridden | Retain to preserve root/home checkpoint boundaries; review vendor tmpfiles changes during upgrades. |
| D11 | Kernel boot | Force `layout=efistub` while disabling the `efistub` USE flag; manual physical registration and custom offline QEMU registration | Keep physical registration manual; retain existing automatic offline QEMU registration during installation. Document manual update commands; broader automatic registration is deferred. |
| D12 | Initramfs | Broad, non-host-only image with explicit modules/drivers | Consolidate distribution policy and retain only justified boot requirements; custom initrd generation remains separate and undefined. |
| D13 | Portage | Git synchronization, host fragments, explicit CPU flags, split debugging, all licenses accepted, package USE and testing keywords | Preserve recorded distribution/host policy except the agreed kernel-policy contradictions and persistent QEMU RAM-build override. |
| D14 | Account | Fixed Graham identity, UID/GID 1000, Zsh, no skeleton files, private home, `wheel,portage` | Retain personal account/access policy; simplify interruption and rerun behavior. |
| D15 | Access | Graham-specific password-required sudo and key-only SSH | Retain explicit access policy. |
| D16 | Configuration management | Live `/` Git work tree with permission-repair hooks | Retain the core architecture and permission protections. |
| D17 | Interactive environment | Shared shell/editor/Git/tmux/SSH defaults, including Zsh `umask 077` | Retain personal environment policy; remove obsolete commented-out configuration. |

Two deviations deserve particular attention:

- **D06 DNS bypass:** [the generated configuration](/home/graham/Projects/agentoo/usr/local/share/agentoo/installer/gentoo-install.sh:2497) uses `env resolvconf=/nonexistent/gentoo-install-resolvconf`. This works because dhcpcd’s hook checks whether that command exists and falls back to writing `resolv.conf`. The agreed replacement is direct dhcpcd ownership through its normal hook, without the fake path. Verify that `sys-apps/systemd -resolvconf` is accepted by the package plan and that no other installed provider redirects the hook. Use the conventional dhcpcd configuration and packaged service. [Upstream dhcpcd resolver hook](https://raw.githubusercontent.com/NetworkConfiguration/dhcpcd/master/hooks/20-resolv.conf), [Gentoo resolvconf flag](https://packages.gentoo.org/useflags/resolvconf).

- **D11 Kernel layout:** this is intentional rather than an obvious mistake. Gentoo’s installkernel packaging normally derives its layout from USE flags; Agentoo overrides that layout while suppressing firmware-registration hooks. Keep physical firmware registration manual, with the existing automatic offline QEMU registration as an explicit installation-time exception. That convenience supports creating guests for ongoing development beyond Agentoo itself. QEMU registration must operate only on the explicitly selected, idle VM variable-store file and never the host's firmware. Normal package operations should still prepare the distribution kernel's modules, initramfs, and EFI files; native automatic registration during later kernel updates remains deferred. [Gentoo installkernel packaging](https://chromium.googlesource.com/external/github.com/gentoo/gentoo/+/526ae3bf0b2e6987328d60eb663593e7d7b2ecb7/sys-kernel/installkernel/installkernel-68.ebuild).

**D10 Systemd storage decision:** retain the ordinary-directory overrides and optional storage-manager masks. Parent Btrfs snapshots omit nested subvolumes, so these deliberate departures keep root/home recovery coverage understandable. Preserve unrelated vendor behavior when reviewing same-named tmpfiles overrides, and check the layout after installation, boot, and updates. ESP capture/restore is unaffected.

## Is the Python necessary

Most embedded Python is replaceable, but a pure-Bash implementation is not a requirement. Prefer whichever implementation makes the retained feature clearer and smaller. Routine command orchestration can move to Bash; keep Python where configuration parsing or permission protections justify it.

| Reference | Location | Purpose | Agreed direction |
|---|---|---|---|
| P01 | [First-boot preflight](/home/graham/Projects/agentoo/root/001-firstboot-verify-and-checkpoint.sh:72) | Run commands, inspect files, compare identities | Simplify in Bash while removing stale-version gating and duplicative capture prerequisites. |
| P02 | [First-boot configuration block](/home/graham/Projects/agentoo/usr/local/share/agentoo/installer/gentoo-install.sh:2464) | Write files, import Wi-Fi profiles, generate credentials | Retain automatic native wpa_supplicant import; remove NetworkManager conversion and obsolete migrations. Use Bash for routine setup where clearer; retain Python parsing if it remains simpler. |
| P03 | [QEMU image discovery](/home/graham/Projects/agentoo/usr/local/share/agentoo/installer/gentoo-install.sh:2837) | Read NUL-separated process arguments and resolve the attached image | Small Bash replacement is feasible; retain accurate target-image identification for the streamlined QEMU creation/handoff workflow without introducing a new framework. |
| P04 | [Permission helper](/home/graham/Projects/agentoo/usr/local/bin/agentoo-permissions:1) | Parse manifest, inspect files, repair ownership/modes | Keep Python and its existing file-descriptor-based protections. |
| P05 | [Checkpoint tool](/home/graham/Projects/agentoo/boot/agentoo/checkpoint.sh:1) | Capture and recovery | Retain shell-only recovery, including ESP capture/restore independent of the installed root. |

### P02 Retain native Wi-Fi import and simplify its scope

The Wi-Fi importer is the largest embedded block: **168 lines**, mixing configuration writes, supplicant parsing, NetworkManager keyfile conversion, WPA key derivation, prompting, migration, and Git exclusions.

**Agreed decision:** retain automatic host-profile discovery and credential import, but support native wpa_supplicant configurations rather than NetworkManager keyfiles. All currently supported installation hosts use wpa_supplicant, so the NetworkManager conversion layer is unnecessary. Keep supported self-contained network blocks, reject unsupported external certificate/include dependencies, and support:

- Automatic discovery/import of supported native wpa_supplicant configurations, with explicit configuration also available.

- Interactive personal WPA provisioning through `wpa_passphrase`.

- Deferring Wi-Fi.

This removes NetworkManager discovery/conversion while preserving automatic native-profile import. Basic discovery and file installation fit Bash; parsing quoted supplicant blocks should be judged on clarity rather than forcing a language change. Keep prompting when no usable profile is found and an explicit configure/defer choice. Passwords must remain out of command arguments, printed output, and Git; if `wpa_passphrase` is used, omit its plaintext-password comment.

### P04 Permission helper protections and the Python dependency

**Agreed decision:** retain the Python permission helper. It validates paths before mutation and modifies opened regular files using file descriptors. A straightforward Bash `stat`/`chown`/`chmod` implementation does not preserve every one of those protections. Removing this dependency is not worth increasing complexity or reducing guarantees.

Removing Agentoo’s Python would not remove Python from Gentoo: Portage itself requires it. Host-side prerequisites were the original concern, but they are a secondary consideration rather than a reason to complicate the retained features. Simplify routine orchestration where Bash is clearer and retain Python where it earns its keep. [Portage dependencies](https://github.com/gentoo/portage#dependencies).

## Additional decisions from the discussion

### DNS ownership and the legacy notes

The [legacy networking notes](/home/graham/Projects/legacy/gentoo-notes/README.md:215) select dhcpcd + wpa_supplicant and packaged per-interface supplicant services. They do not state a rationale for avoiding resolvconf. The bypass appears in the later installer.

The agreed core uses direct dhcpcd ownership of `/etc/resolv.conf`, minimizing installed components and running services. Openresolv would coordinate DNS from several producers; systemd-resolved would add caching and per-link DNS routing with explicit integration. Neither is required for the present core. Gentoo's systemd `resolvconf` USE flag supplies a compatibility symlink, so leaving it present while disabling resolved can misdirect dhcpcd's updates. Prefer removing that unnecessary shim through package policy, subject to the actual dependency/provider check in T05. [Gentoo resolvconf flag](https://packages.gentoo.org/useflags/resolvconf), [dhcpcd hook](https://raw.githubusercontent.com/NetworkConfiguration/dhcpcd/master/hooks/20-resolv.conf).

### Logging defaults

The 256 MiB/512 MiB limits came from the legacy installer commit `bcfe67b`, which introduced bounded persistent journald; the scratch notes do not justify those particular numbers. Upstream journald scales maximum use and free-space limits with filesystem size, capped at 4 GiB. The free-space setting constrains journald rather than reserving disk against other writers. The user has had previous-boot journal history on Gentoo without custom logging configuration.

Use packaged defaults for both storage and retention. Remove the Agentoo drop-in, preserve existing logs/directories, and report previous-boot history in verification instead of requiring a custom persistence policy. [Upstream journal configuration](https://raw.githubusercontent.com/systemd/systemd/main/man/journald.conf.xml).

### Manual physical EFI registration and the QEMU convenience

**Required for physical targets and later manual kernel updates:** document the manual command, including the version, matching initramfs, target ESP/disk, and the Startop full-device-path exception. A new helper program is not required. Retain the existing installation-time command output. Retain the existing automatic offline QEMU registration during installation and its boot handoff guidance; do not replace that convenience with a manual-only guest-creation workflow.

**Optional convenience:** investigate printing a fully populated copy/paste command after a distribution-kernel update. Much of the formatting already exists in [print_physical_kernel_boot_commands](/home/graham/Projects/agentoo/usr/local/share/agentoo/installer/gentoo-install.sh:1990). Installation-time printing can reuse the known version, command line, disk, and ESP identity. Update-time printing would need a small local kernel-install notification hook or equivalent package-supported notification point: take the release from the update invocation, read the distribution command line, identify the mounted ESP's disk/partition, preserve Startop's path option, and quote arguments safely.

That hook must only print, never run firmware commands or change BootOrder. It should not turn inability to print guidance into a failed kernel update. Keep the documented command as the fallback. Assess the actual hook timing: kernel-install may run more than once during an emerge transaction, so “printed by a hook” does not guarantee one message at the very end of emerge. This is modest orchestration in principle, but introduces one maintained hook; implement it only if the resulting code stays small and clear. This convenience is separate from native automatic firmware registration during kernel updates, which remains deferred. The existing offline QEMU installer registration is retained independently.

## Other worthwhile simplifications

**S01 Consolidate repeated installer plumbing.** Partition-path derivation appears throughout the phases; chroot mount checks and temporary-helper execution are repeated. A few small helpers would remove duplication without creating a framework.

**S02 Use one argument-validation contract.** For example, initial validation permits a timezone such as `UTC`, while Portage-foundation validation requires a slash. Validate input once, then validate actual target state at phase boundaries.

**S03 Make failure behavior consistent.** Bootstrap and Portage failures attempt to dismantle the target; update and kernel failures preserve it for retry. Keeping a prepared target mounted after a recoverable installation failure would make the workflow easier to understand. Retain cleanup of temporary files and newly acquired resources.

**S04 Remove obsolete migration branches.** Old Wi-Fi unit/rule migration and old kernel-policy filename cleanup do not belong indefinitely in the fresh-install core. Git already records their history.

**S05 Move namespace recovery out of ordinary handoff.** It is useful recovery logic, but scanning other processes and entering mount namespaces is a substantial extension of an installer’s responsibility. Keep it as an explicit recovery procedure/tool.

**S06 Stop duplicating credential configuration — accepted.** Wi-Fi credentials currently live in a staging configuration and are copied into per-interface files. Preserve automatic native-profile import, but write the configurations actually consumed by packaged services and remove unnecessary persistent staging copies. Keep secrets root-only and excluded from Git.

**S07 Separate diagnostic output from required assertions.** Commands showing routes, failed units, or timer schedules do not necessarily establish that the desired condition holds. Explicit assertions would make “verification passed” more meaningful.

**S08 Give checkpoint preflight one owner.** First-boot preflight requires `efibootmgr`, although checkpoint creation deliberately handles its absence. Keep capture prerequisites in the checkpoint tool and boot-health checks in the verifier.

**S09 Clarify account reruns.** User setup resets the password on every run, but Git identity setup is offered only on account creation. An interrupted first run can therefore skip identity setup permanently on retry. A clearly one-time provisioning script, with a small completion check, would be easier to reason about.

**S10 Move long explanatory material into the runbook — deferred.** The installer is 3,024 lines and includes extensive embedded walkthroughs. Keep those walkthroughs and `--verbose` explanations in the installer for now. Simplify executable logic without treating line count as a goal.

**S11 Remove obsolete commented-out configuration elsewhere as well.**

## Agreed minimal core and implementation sequence

Retain the seven meaningful installation phases, signed release verification, explicit disk identity checks, encrypted Btrfs layout, stable distribution fallback, packaged networking services, native configuration fragments, and shell-only recovery including ESP capture/restore. Keep manual physical firmware registration and automatic offline QEMU installer registration, automatic native wpa_supplicant import, optional host-backed RAM builds during installation, and the embedded walkthroughs. Physical installation runs on the destination hardware; the custom-kernel path remains separate and undefined.

The revised sequence below supersedes the original proposals to remove automatic Wi-Fi import, enforce pure Bash, or move the walkthroughs. The concrete T-actions that follow include affected components and completion checks.

1. **R01** Fix the @/@home layout contract and deferred-Wi-Fi verification; retain all checkpoint components.

2. **R02** Consolidate stable distribution-kernel/firmware policy and remove obsolete migration branches; keep physical registration manual and retain offline QEMU installer registration.

3. **R03** Make QEMU RAM builds an optional installation-time choice and restore normal disk-backed build defaults after boot.

4. **R04** Retain automatic native wpa_supplicant import, remove NetworkManager conversion, and use normal dhcpcd configuration with direct DNS ownership and packaged logging defaults.

5. **R05** Simplify first-boot preflight and routine setup in Bash where clearer; retain the Python permission helper and parsing where justified.

6. **R06** Consolidate installer plumbing, make retry behavior consistent, and move mount-namespace recovery into an explicit recovery procedure; preserve embedded documentation.

7. **R07** Document manual physical/update EFI registration, preserve the QEMU installer convenience, and record the deferred investigation of broader automatic registration; assess a command-printing hook as an optional convenience, not a requirement.

The disk-erasure checks, signature verification, mount identity checks, and recovery integrity checks are the parts I would preserve most carefully. They protect against costly mistakes; the better opportunities for reduction are unsupported flexibility, duplicated policy, automatic discovery, and historical compatibility code.

## Concrete actions to take

All actions below are pending. Implement in small, reviewable groups; keep the retained behavior in the completion checks. The status **optional** or **deferred** is explicit where applicable.

### T01 Fix the installation and recovery contract

**References:** A01, A03, D02, R01. **Components:** installer arguments, disk setup, kernel/first-boot option propagation, runbook.

Remove `--root-subvol`/`--home-subvol` and their environment overrides; use fixed `@`/`@home` names everywhere. Remove validation/propagation needed only for alternative names. Document that physical installation runs on the destination hardware, with QEMU/NBD as a separate supported workflow.

**Done when:** install mounts, fstab, kernel parameters, and checkpoint capture/restore all agree on the fixed layout; unsupported layout options fail before any disk mutation. ESP capture/restore remains intact.

### T02 Consolidate the distribution fallback policy

**References:** A04, A05, D11–D13, R02. **Components:** tracked Portage fragments, generated kernel policy, Dracut/installkernel configuration, post-boot verifier.

Make stable `gentoo-kernel-bin` policy a single tracked source of truth. Remove opposing common/kernel-phase firmware `savedconfig` and distribution-provider keyword settings. Use packaged module/initramfs/kernel installation and retain only explicit overrides needed for encrypted Btrfs boot and manual physical firmware registration and the separate offline QEMU installer workflow. Prefer the conventional `/etc/kernel/cmdline` as the distribution command-line record rather than maintaining duplicate copies. Treat the recorded installation release as handoff data, not a permanent running-kernel requirement.

**Done when:** a distribution-kernel update prepares matching modules/initramfs/EFI files without re-running the installer or maintaining a new version-tracking hook; fallback verification is independent of a future custom running kernel. No custom-image implementation is introduced.

### T03 Keep physical registration manual and retain automatic QEMU setup

**References:** D11, R07. **Components:** kernel phase, QEMU firmware workflow, installation/update runbook.

Retain the existing automatic offline QEMU variable-store registration in the installer, including explicit store selection, idle-store checks, preservation of unrelated entries/variables, backups, atomic publication, and safe retry behavior. Keep the QEMU boot handoff convenient for creating general development guests. Physical firmware registration remains manual. Document physical and later-update commands with version/initramfs substitution, ESP/disk identification, the Startop full-device-path requirement, inspection of existing entries, and preservation of a tested fallback. Reuse existing installation-time printing; no new helper is required. This exception retains existing QEMU creation behavior, not new automatic registration inside a booted guest after kernel updates.

**Done when:** physical installer/package operations do not write motherboard firmware entries; a fresh QEMU installation automatically prepares only the explicitly selected, idle VM firmware store and boots using the handoff guidance. Retrying registration preserves other entries and variables and does not add duplicate equivalent entries. Host firmware remains untouched. Later distribution-kernel updates have documented manual registration guidance.

### T04 Make RAM build storage temporary for QEMU

**References:** A06, R03. **Components:** QEMU make.conf fragment, installer package-operation wrappers, runbook.

Remove QEMU's permanent `PORTAGE_TMPDIR`/`PORTAGE_TMPFS` override. Provide a simple optional installation-time RAM-build choice that reaches every relevant target package transaction, including child chroot invocations. Keep explicit physical-host policy. State that actual tmpfs capacity and available memory limit builds.

**Done when:** the opted-in host-backed install builds in the host-visible `/dev/shm`; ordinary guest package operations after boot use the normal disk-backed location. Installation without the opt-in remains functional.

### T05 Restore the normal dhcpcd paths and direct DNS handling

**References:** D04–D07, R04. **Components:** first-boot file writer, service policy, Portage package USE policy.

Use the packaged dhcpcd service and `/etc/dhcpcd.conf`; remove the alternate config path and ExecStart replacement. Keep only required network policy, including avoiding duplicate supplicant startup. Verify the dependency plan for `sys-apps/systemd -resolvconf` and inspect other resolver providers, then remove the nonexistent-command workaround. Keep direct dhcpcd DNS ownership and competing target network/DNS services disabled.

**Done when:** DHCP routes and DNS work after first boot and reboot, no inactive resolver shim receives updates, and no extra DNS service/coordinator is added.

### T06 Narrow Wi-Fi import without removing it

**References:** A02, A03, P02, S06, R04. **Components:** importer, target supplicant configuration, post-boot networking checks.

Add an explicit configure/defer choice for physical targets. Preserve native wpa_supplicant profile discovery/import and prompting when no supported profile exists; remove NetworkManager keyfile parsing/conversion. Write root-only packaged per-interface configuration directly instead of retaining unnecessary credential staging copies. Keep secrets excluded from Git and output. Require supplicant health only for configured/enabled interfaces; retain QEMU's Ethernet-only path.

**Done when:** native import and manual prompting work on a supported physical host; Ethernet-only/deferred-Wi-Fi verification succeeds; configured Wi-Fi failures remain visible. The language choice follows the simplified parser's clarity.

### T07 Inherit packaged logging defaults

**References:** D08. **Components:** first-boot writer, diagnostics, runbook.

Stop generating the Agentoo journald drop-in, including Storage and numeric size overrides. For an existing installation, remove only that known Agentoo-owned drop-in; preserve logs and journal directories. Remove diagnostic requirements for Agentoo-specific persistence/retention and report actual journal history.

**Done when:** the installed logging behavior comes from packaged defaults and previous-boot history is inspected after reboot. No historical logs are deleted by the change.

### T08 Consolidate installer plumbing and retry behavior

**References:** S01–S05, S11, R02, R06. **Components:** installer helpers, phase cleanup, recovery documentation, shared configuration.

Consolidate partition derivation, argument validation, chroot mount checks, and temporary-helper execution into a few small helpers. Align timezone/name validation across entry points. On recoverable phase failure, preserve the prepared target for inspection/retry while cleaning invocation-owned temporary files; keep safe rollback of newly created disk-setup resources. Remove obsolete Wi-Fi/kernel filename migrations and stale commented-out configuration. Move mount-namespace scanning/teardown out of normal handoff into an explicit recovery procedure.

**Done when:** phase retries have documented, consistent mount/mapper behavior; ordinary handoff does not enter other processes' namespaces. Disk-erasure guards, signature checks, and mount identity checks remain. Keep embedded walkthroughs and `--verbose` material.

### T09 Simplify verification and account reruns

**References:** P01, P03, S07–S09, R05–R06. **Components:** both post-boot scripts, checkpoint preflight, QEMU image discovery.

Separate informational diagnostics from assertions that determine success. Let the checkpoint tool own capture prerequisites; remove the verifier's redundant mandatory `efibootmgr` check. Replace stale-release gating as specified in T02 and make routine preflight orchestration clearer in Bash. Make interrupted account setup resumable without forcing a password reset on every rerun or permanently losing the Git-identity setup opportunity; preserve existing home contents and supplementary groups. Use a small Bash replacement for QEMU image discovery only if it improves clarity.

**Done when:** required failed conditions produce accurate failures, information-only commands do not invent requirements, and an interrupted account setup can complete on retry. Keep the existing access policy.

### T10 Assess optional EFI command notification

**References:** D11, R07. **Status:** optional convenience.

Assess reusing the existing formatting in a small print-only update hook, as described above. Prefer release data supplied by kernel-install over an extra persistent “latest version” file. Check physical disk/partition identification, quoting, Startop behavior, and duplicate invocations.

**Done when:** either a small, tested notification is justified or the documented command alone is retained. Lack of notification must not block distribution-kernel updates. No firmware command is executed by the notification.

### T11 Record deferred automatic registration work

**References:** D11, R07. **Status:** create a backlog card; investigation and implementation remain deferred.

Create a card titled **Investigate automatic distribution kernel EFI registration**. Compare native packaged registration mechanisms with the manual physical/update workflow; identify entry/BootOrder changes; verify offline installation cannot touch host firmware; cover physical firmware requirements and any proposed extension to guest update registration; test install/update/reboot/failure/removal while preserving a known-working fallback. Treat the existing offline QEMU installer registration as retained functionality, not deferred work. The eventual recommendation must keep the custom-image path independent and explain explicit enablement.

**Done when:** the repository backlog card records those boundaries and completion checks. Creating the card does not enable broader automatic registration or remove the existing offline QEMU installer convenience.

### T12 Validate the retained core after implementation

**References:** A01–A06, D04–D12, P05.

Run syntax/static checks appropriate to the changed scripts, targeted retry/defer/identity fixtures, then a fresh QEMU/NBD installation through automatic offline VM registration, first boot, reboot, and a distribution-kernel update with manual registration guidance. Verify temporary-versus-persistent build storage, routes/DNS, packaged journal behavior, scrub scheduling, and absence of nested subvolumes. Exercise native Wi-Fi import/authentication on supported physical hardware; record any hardware coverage that remains unavailable.

Verify checkpoint creation and recovery for system/home/ESP, including default home preservation, saved EFI restoration with later additions preserved, unchanged firmware entries, and recovery without the installed root. Keep meaningful destructive recovery validation on disposable targets.

**Done when:** the changed production paths and retained recovery behavior pass, with limitations recorded accurately. This action list does not claim those checks have already run.

## Retained behavior and deferred work

Keep stable distribution fallback availability, independent custom-image boundaries, signed release verification, disk/mount identity protections, root/home/ESP checkpoints, root-independent shell recovery, the scrub timer, ordinary-directory systemd storage policy, permission-helper safeguards, and the existing personal account/access/environment policy.

**S10 remains deferred:** embedded walkthroughs and verbose explanations stay in the installer. **Broader automatic firmware registration remains deferred:** T11 records the future investigation; retain the existing automatic offline QEMU installer registration for streamlined guest creation. **Pure Bash is not a goal in itself:** retain the permission helper's Python and choose parsing tools by clarity. **The custom kernel path remains undefined:** this cleanup only preserves its independence.

## Implementation progress

Use this tracker alongside the detailed T-actions above. Record what changed and the corresponding validation in the work log before marking an action complete.

| Action | Status | Implementation and validation record |
|---|---|---|
| T01 Installation and recovery contract | Validated on QEMU | Fixed @/@home; destination-hardware physical contract; offline system/home/EFI restore passed. |
| T02 Distribution fallback policy | Validated on QEMU | Packaged regeneration and reboot passed; absent ESP stops kernel-install. A version-to-version upgrade remains untested. |
| T03 Manual physical registration and automatic QEMU setup | Validated on QEMU | Initial offline registration booted; update guidance printed without firmware changes. Physical registration remains manual. |
| T04 Temporary QEMU RAM builds | Revised after review; focused checks passed | RAM builds default on for all installer invocations; --no-ram-builds selects /var/tmp and propagates to children. No persistent QEMU override. |
| T05 Normal dhcpcd paths and direct DNS | Complete | Packaged service/configuration; systemd -resolvconf; provider check. |
| T06 Native Wi-Fi import and deferred configuration | Revised after review; focused checks passed | Embedded Bash copies a host native configuration unchanged or prompts/defers; no parser or companion installer file. Hardware authentication remains untested. |
| T07 Packaged logging defaults | Complete | Packaged journal history and tagged previous-boot message survived reboot. |
| T08 Installer plumbing and retries | Implemented; focused checks passed | Shared partition/chroot helpers; mounted targets retained on failure; consistent retry selections. |
| T09 Verification and account reruns | Complete | Guest diagnostics and interrupted/normal account reruns passed; password, home, groups and partial Git identity preserved. |
| T10 EFI command notification | Implemented; focused and offline checks passed | 27-line print-only update hook; never executes firmware changes; documented fallback. |
| T11 Automatic registration investigation card | Complete; investigation deferred | Backlog 008 records future native registration; QEMU exception retained. |
| T12 Retained-core validation | Available closeout checks passed; limits recorded | Installation/boot, capture/cache cleanup, account retries, regeneration/reboot, scrub/journal/networking and offline system/home/EFI recovery passed. Physical Wi-Fi authentication and a version-to-version kernel upgrade remain untested. |

## Work log

### 2026-10-12 Opened from the agreed audit

- Preserved the complete current Page, including the rationale, categorized findings, tables, stable references, revised decisions, and concrete actions.
- Retained automatic offline QEMU registration as the explicit convenience exception to manual physical firmware registration.
- No installer, post-boot, or deployed-system behavior changed in opening this card.
- Registered this card in the managed permissions manifest as root-owned, mode 0644.
- Compared the repository against the original audit baseline before opening the card. Subsequent commits through `00fe99e` retain the main findings, while adding root's Zsh login, the Caps Lock-to-Control console keymap, binary-package cache cleanup, simpler Git command passthrough, and the self-contained-recovery backlog card.
- During implementation, preserve the current checkpoint cleanup of both distfiles and binary-package caches and include it in T12 validation. Treat the new shell/keymap settings as deliberate personal policy.
- Self-contained recovery remains separately tracked in [006-self-contained-recovery.md](../Backlog/006-self-contained-recovery.md). This card does not choose or implement that future recovery design.

For each implementation entry, record the date, affected T-actions, changes and rationale, validation actually performed, relevant commit references when available, and any remaining limitations. Later decisions should identify which original decision they amend.


### 2026-10-12 Implementation and initial validation

- Implemented T01–T11 in the working tree against repository baseline `00fe99e`. The audit snapshot above remains unchanged. No main-repository commit has been made.
- Consolidated the distribution fallback policy into tracked payload files and recorded the local ESP identity before package hooks can run. Kept custom image work separate and retained automatic offline QEMU setup. Added a small optional print-only update notification and deferred native automatic registration in Backlog 008.
- Removed custom networking service paths, the fake resolvconf executable path, NetworkManager conversion, generated journald policy, alternate root/home layouts, and historical migration code. Preserved scrub/storage masks, root Zsh/keymap policy, verbose walkthroughs, and checkpoint cache cleanup.
- Consolidated chroot execution, partition discovery, and temporary file cleanup. Failed phases preserve prepared mounts. Portage retries preserve checkout edits and refuse a changed source/branch/host selection. Replaced the embedded first-boot writer and QEMU image discovery with Bash. Native Wi-Fi parsing stays in a small standalone Python helper; the permission helper remains Python.
- Reworked post-boot diagnostics so optional information does not determine success, unconfigured Wi-Fi is skipped, and fallback files are checked independently of the running release. Account reruns retain a usable password and resume an interrupted optional Git-identity choice.
- Passed Bash/shell/Python syntax checks, ShellCheck 0.11.0 at warning severity (excluding dynamic source, prose quote, and intentional privileged terminal-redirection notices), scrub-unit verification, diff whitespace checks, and focused parser/writer/chroot/option tests. Permission coverage includes all 76 payload files. These checks do not establish full boot/recovery success.
- Started a fresh installation using the production installer and a snapshot of the implementation at `/tmp/agentoo-validation-2adt9mne/test.qcow2`, with explicitly authorized disposable test passwords. Verified disk setup, signed stage3 bootstrap, checkout/permissions, repository authentication, and progress through real package reconciliation. Existing VM images and host configuration remain untouched. Boot, checkpoint, account reruns, and recovery validation remain pending.

### 2026-10-12 Production installation results and remaining validation

- The fresh disposable target completed real disk setup, authenticated stage3 bootstrap, Portage foundation, the full initial world update, distribution-kernel installation/configuration, automatic offline QEMU EFI registration, and first-boot configuration. The maintained fallback is `6.18.54-gentoo-dist-bin`; matching EFI kernel/initramfs and modules were verified. Kernel-install ran the tracked ESP guard and print-only hook successfully in the offline target.
- The real package plan accepted `systemd -resolvconf`, installkernel without the firmware-writing efistub plugin, and the stable binary distribution fallback. First-boot setup found the packaged dhcpcd configuration, enabled its normal service, and validated UUID fstab entries. These are offline checks; guest DHCP/DNS and booted service health remain untested.
- Fresh installation caught a merged-directory shell-path issue: `command -v zsh` returned `/usr/sbin/zsh`, while `/etc/shells` listed its canonical `/usr/bin/zsh` path. Both installer and account setup now resolve that path before validation. Resuming only the failed first-boot phase succeeded; disk setup was not repeated. Added a protected-configuration-update gate before first-boot completion and disabled the kernel-phase diff pager.
- Reviewed the Zsh package's protected zprofile update and retained the intended shared Agentoo login configuration. Gentoo dispatch-conf requires an interactive terminal type; the agent terminal's `dumb` setting was unsuitable, so validation used `TERM=xterm`. This is a validation-environment adjustment, not a deployed policy change.
- Focused notification fixtures passed for QEMU and Startop command printing and custom-image independence, without executing firmware commands. Re-ran syntax, ShellCheck, permission coverage, and diff-whitespace checks after the fixes.
- Ordinary handoff unmounted the target in the caller's namespace, then correctly refused to close a mapping still held by other host mount namespaces. Inspection identified service-private `/tmp` overlays hiding propagated mounts in the underlying mount tree. Normal recursive unmounts failed because the copied target paths were inaccessible. No forced/lazy unmounts, unrelated service restarts, or firmware writes were performed. This is a host cleanup limitation, not successful handoff or guest boot.
- Preserved `/tmp/agentoo-validation-2adt9mne/test.qcow2`, its dedicated OVMF VARS file, `/dev/nbd0` attachment, and `/dev/mapper/agentoo-audit-test`. No package builds remain active. A normal host reboot releases the namespace references and NBD connection; `/tmp` is tmpfs here, so the disposable image will also disappear at reboot. A later validation run must preserve the image outside `/tmp` before reboot or build a new target.
- Boot/reboot, a later distribution-kernel update, online checkpoint creation/cache cleanup, account reruns, and offline system/home/ESP recovery remain pending. Physical Wi-Fi authentication also remains unavailable. T12 is deliberately open. Keep future test mount roots outside service-private `/tmp` overlays; image storage may be separate.

### 2026-10-12 Guest validation and continuation checkpoint

- Stopped investigating host mount-namespace cleanup after identifying service-private `/tmp` overlays. The original `/dev/nbd0` and `agentoo-audit-test` mapping remain preserved; do not disconnect underneath those mounts. A host reboot will release them. No unrelated services were restarted.
- In one bounded privileged operation, verified the test mapping/image identity, mounted its filesystem in a private child namespace, froze only that filesystem, copied the flushed qcow2 image, thawed it, and unmounted the temporary copy mount. The persistent validation image and dedicated VARS store are now at `/home/graham/.codex/visualizations/2026/10/12/01a131d1-1f1f-7460-ba31-9582229c8549/agentoo-validation/`. The copies are user-owned and the VM runs as Graham with KVM, no forwarded ports. Original test attachments are independent of this copy.
- The persistent copy booted through the automatically prepared QEMU EFI entry, unlocked LUKS, and accepted the test root login. The actual full post-boot verifier passed mount/fallback identity, DHCP, DNS, HTTPS, time synchronization, failed-service, and scrub-timer checks. It created system, home, and EFI checkpoint `fresh-install-20261013T021040Z-905`. Both package caches contain zero files after the standard cleanup. Booted Portage reports `/var/tmp`, confirming that installer RAM storage is not persistent policy.
- Account setup installed its normal dependencies, validated sudo/SSH configuration, created Graham with the intended UID/GID/groups and Zsh, and set an authorized disposable test password. Intentionally interrupted at the optional Git-identity prompt to exercise the interrupted-run case. No identity-completion marker should exist yet. The second run remains to be tested. No package operation is active.
- Moved QEMU serial-console arguments into the canonical local kernel command line so later printed registration guidance preserves console access. Removed their duplicate formatting from offline registration. The running test guest still has the preceding local record (the initial EFI entry supplied those arguments); update that test-local record before testing regeneration guidance.
- Continuation state: QEMU serial terminal session `80130` is idle at the guest root Zsh prompt. The VM is booted from the persistent copy. The main repository remains uncommitted at baseline `00fe99e`. The audit snapshot above has not been rewritten.

Remaining work:

1. Re-run account setup after the deliberate interruption; verify the password is preserved, Git identity completes, home contents/groups remain intact, and a further normal rerun succeeds.
2. Exercise packaged distribution-kernel regeneration on the booted guest, inspect the print-only manual registration command, and verify firmware entries remain unchanged. A genuine version-to-version upgrade is not yet covered.
3. Reboot the guest and rerun diagnostics; report packaged journal persistence and scrub behavior accurately. Stop the guest cleanly afterward.
4. Validate offline system/home/EFI recovery, including default home preservation and later EFI additions, from an environment independent of the installed root. This remains a separate validation gap; do not resume host namespace cleanup as part of it.
5. Physical Wi-Fi authentication remains unavailable; parser/secret-file fixtures passed. Final review/static checks and tracker updates remain before implementation handoff.

### 2026-10-13 S11 comment cleanup correction

- At the user’s request, restored useful zshrc explanations for command timing, remote terminfo installation, and the color palette, along with section headings and fold boundaries. Kept obsolete commented-out configuration removed. The keybindings heading reflects the retained functions; the obsolete abbreviation implementation stays removed.
- Verified executable content still matches the repository baseline and the diff has no whitespace errors. Git configuration and zprofile cleanup remain comment-only. Further implementation/guest validation remains on hold during review.

### 2026-10-13 Diff review: comments 1–8

- **C01:** inspected Gentoo installkernel 68 hooks and systemd 261 source. An explicit BOOT_ROOT bypasses automatic ESP discovery; Gentoo’s efistub copy hook creates/copies files in that directory without comparing the installation’s ESP UUID. Kept the small stronger identity guard and clarified its rationale; left it unstaged for review.
- **C02/C08:** clarified that transaction environment overrides reach the chroot world update. Amended T04’s earlier opt-in decision: RAM builds are now the default for every installer invocation. `--no-ram-builds` selects `/var/tmp`, overriding even a machine-specific RAM-build setting for these transactions, and is propagated to child invocations. Booted QEMU package operations still inherit the normal disk-backed default.
- **C03:** systemd’s kernel-install flag supplies the program used by installkernel’s systemd backend; it is enabled by default and required by that dependency. Removed the redundant explicit sys-apps/systemd kernel-install line from Agentoo package policy.
- **C04/C05:** restored SSH Include precedence/account-local host explanations and enabled the user-requested interactive Zsh core-size limit. Other useful Zsh explanations remain restored; obsolete commented-out snippets remain removed.
- **C06/C07:** amended T06’s parser decision in favor of the newly clarified minimal contract. Deleted the standalone Python importer. A 49-line embedded Bash function copies the matching per-interface or common native host file unchanged, or prompts for SSID/password (blank SSID defers). It preserves existing target credentials, installs mode 0600, uses wpa_passphrase via stdin and strips its plaintext-password comment. Full-file copies retain any external references; corresponding certificates/credentials must be provisioned separately.
- Added the standalone curl download/run example at the installer’s top. Verified its raw GitHub URL returns HTTP 200. Downloading to a regular script file lets child chroot phases copy the same source; no local repository checkout or companion installer script is required. Stage3 and target configuration remain fetched installation inputs, including their deployed runtime tools. These working-tree changes are not yet published by that URL.
- Passed Bash syntax, ShellCheck at the previously recorded severity/exclusions, whitespace checks, and focused fixtures for default/disabled RAM storage, actual child phase argument dispatch, unchanged native file copying, existing credential preservation, common-file fallback, hidden password input/plaintext-comment removal, open-network SSID encoding, deferred Wi-Fi, and complete permission-manifest coverage. No new guest/hardware run was performed during this review. Earlier end-to-end results apply to the preceding implementation, not these revised Wi-Fi/RAM choices.
- Prepared a partial Git index: unrelated hunks are staged; commented areas and their related documentation/permission entries remain unstaged. Shared mixed hunks remain unstaged rather than include a reviewed area accidentally. No commit is created.

### 2026-10-13 Manual compaction checkpoint — testing not started

- User has finished diff comments and asked for a manual compaction before remaining testing. Do not start tests until the user resumes after compaction. This is a continuation checkpoint, not another guest filesystem snapshot.
- Remaining closeout work: (1) standalone installer execution outside a checkout, including a child chroot phase; (2) complete the interrupted account setup and verify normal reruns/password/home/group preservation; (3) packaged fallback regeneration, print-only guidance, unchanged firmware entries, and clear failure with the test ESP unmounted; (4) reboot diagnostics/networking/journal/scrub checks; (5) offline system/home/EFI recovery from an environment independent of the installed root, including preserved home and later EFI additions; then final diff/static/permission review, staging of approved changes, and work-log update. A real version-to-version kernel upgrade remains distinct from regeneration.
- These tests are authorized on disposable targets, including disposable test passwords. Reuse the persistent validation VM where possible; confirm its current identity/state before operations. Only host administrator authentication and unavailable physical Wi-Fi hardware may require user involvement. Consolidate any necessary privileged operations. Do not touch the user's existing VM or resume host namespace cleanup.
- Retain current `BOOT_ROOT=/boot` and the custom ESP guard. The follow-up discussion established that automatic discovery also falls back to an ordinary `/boot` directory when no boot partition is found; dropping the override does not provide a missing-mount failure by itself. Simplifying the UUID comparison was discussed as an option, but no removal was requested or implemented.
- The original agreed audit snapshot remains untouched. Latest review decisions are in the preceding entry. Preserve the partial index: unrelated hunks and helpers are staged; reviewed areas and related/mixed hunks remain unstaged. User has now said there are no further comments; final staging is part of closeout, after testing and final review. No commit or publication has been requested.
- Persistent validation files: `/home/graham/.codex/visualizations/2026/10/12/01a131d1-1f1f-7460-ba31-9582229c8549/agentoo-validation/test.qcow2` and `OVMF_VARS.4m.fd`. Last observed serial session: `80130`, guest root prompt after intentional account-setup interruption. Check whether that session still exists; do not assume it remains live across compaction. Guest checkpoint: `fresh-install-20261013T021040Z-905`; fallback: `6.18.54-gentoo-dist-bin`.
- Original test attachment, if still present: `/dev/nbd0` → `/tmp/agentoo-validation-2adt9mne/test.qcow2`, mapping `agentoo-audit-test` → `/dev/nbd0p2`. It remains independently held by host service namespaces. Do not disconnect it under mounted filesystems or investigate its cleanup further for this task. The persistent guest copy is independent; a future normal host reboot clears the original temporary attachment.
- Transient focused review harness: `/tmp/agentoo-review-checks.py`; official ShellCheck: `/tmp/shellcheck-v0.11.0/shellcheck`. Earlier `/tmp/agentoo-checks.py` targets the superseded Python importer and RAM opt-in and must not be reused unchanged. If temporary files no longer exist, recreate only relevant checks.
- A durable source/index/context backup is saved under the task artifact directory in `implementation-checkpoint-20261013`. It contains code snapshots and Git patches, not passwords. Previously used disposable passphrases stay out of saved files, command arguments, and diagnostic output.


### 2026-10-13 Focused closeout verification

- Resumed after manual compaction and compared all 22 checkpointed files against their saved SHA-256 values: no intervening changes. Reused the persistent disposable QEMU guest; did not touch the user's existing VM or resume the host namespace cleanup detour. No new host privileged operation was required during these checks.
- Completed the deliberately interrupted account setup. The complete `/etc/shadow` checksum stayed unchanged; home marker and UID/GID/groups survived. An existing user-owned Git author name was preserved while the missing email was filled. The completion marker was written; a further ordinary rerun preserved state and omitted the Git prompt.
- Transferred the current reviewed installer and kernel policy/hooks into the guest. The installer ran as a regular file under `/run`, outside a checkout; its SHA-256 matched the current source. Invoked its actual `run_chroot_phase` helper with `--help`: the copied script executed through chroot with the clean environment, returned successfully and removed its temporary helper. Help differs only by the invoked script path. This is a real child launch/cleanup check, not a second complete standalone installation. Earlier full production installation results and the targeted argument/storage fixtures supply the remaining coverage. The public curl URL still serves the published revision, not these uncommitted changes.
- Ran the actual packaged `emerge --config sys-kernel/gentoo-kernel-bin` for `6.18.54-gentoo-dist-bin`; Dracut generation and installkernel copy passed. The current print-only hook emitted the disk/partition/release/canonical-console command. `efibootmgr -v` was byte-for-byte unchanged. With the test ESP unmounted, actual `kernel-install add` failed at the guard with status 1 and the intended diagnostic; remounted it afterward. This validates regeneration, not a version-to-version upgrade. The guest-local command line was amended to the reviewed QEMU console policy before regeneration.
- Guest diagnostics passed before and after reboot; machine ID stayed `696876e816634864ad9bda6d3c7579f0`. Packaged journald listed both boots and retained the tagged previous-boot message. DHCP/DNS/HTTPS and time-service checks passed, no failed units remained, and booted Portage reported `/var/tmp`. The monthly scrub service finished with no errors over 4.23 GiB; timer remained enabled and active.
- Exercised the real ESP checkpoint implementation from a temporary Dracut pre-mount recovery environment inside the disposable VM. Verified live vda/LUKS/ESP identities and that the installed root was not mounted during inspection/restoration. The recovery image carried the documented tools; its omitted `sync` was copied into RAM before proceeding, with the briefly read-only-mounted target unmounted again. Declined the initial prompt while correcting that environment. No recovery feature or alternate installer mode was added to the repository.
- Inspected checkpoint `fresh-install-20261013T021040Z-905` and verified its archive checksums. Default restore replaced a changed system marker and EFI marker with their baseline contents, preserved changed home contents and a later EFI file, and left firmware entries unchanged. Explicit `--home` then restored the home marker while retaining system/EFI state. Root and home remained flat subvolumes; the named checkpoint was retained. A temporary guest-only recovery entry/image supplied this environment; removed them before rebooting through the original entry. Firmware comparisons surround the restores themselves, separately from this explicit test preparation/cleanup.
- Repeated focused Bash/RAM/Wi-Fi/permission fixtures, syntax, ShellCheck at the recorded severity/exclusions, and staged/unstaged whitespace checks: all passed. No additional implementation changes were needed during closeout.
- Coverage limits: physical Wi-Fi authentication is unavailable on this VM; native copying/prompt/defer behavior has fixture coverage. A real version-to-version distribution-kernel upgrade and physical firmware registration were not exercised. Full fresh installation preceded the last RAM/Wi-Fi review amendments; their current behavior has focused coverage rather than another destructive full installation.
- After recovery, booted through the original Boot0000 entry, confirmed baseline system/home/EFI markers plus the retained later EFI file, and passed guest diagnostics again. Removed temporary recovery boot entry/image; BootOrder returned to its original value. Powered the guest off normally; its QEMU session exited with status 0. The persistent disposable image and VARS remain available, while the older independent host attachment remains untouched as previously documented.
- Final handoff: staged the remaining reviewed changes and this updated work log. No repository commit or publication was made. The historical audit and original rationale remain intact; this Open card remains the implementation record.

### 2026-10-13 Physical installation: defer first-boot configuration merging

- Physical thinktop testing reached first-boot-foundation and paused on Portage's
  protected `/etc/zsh/zprofile` update. The user requested the earlier behavior:
  report these pending updates, continue installation, and leave merging until
  after boot.
- Replaced the first-boot-foundation configuration-update failure with a report
  and `sudo dispatch-conf` reminder; updated the runbook. Existing configuration
  files and Portage's pending update files remain intact. The earlier system-update
  review and kernel-phase checks retain their existing behavior.
- Checked Bash syntax, ShellCheck at the established severity/exclusions, and
  whitespace. This reporting-only change does not require another VM installation;
  the user's mounted physical installation supplies the next execution check.
