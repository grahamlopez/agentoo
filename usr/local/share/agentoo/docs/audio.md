# Audio

## Audio startup and compatibility

Run these commands as the desktop user after verifying their user manager:

```sh
systemctl --user enable --now pipewire.service pipewire-pulse.socket wireplumber.service
systemctl --user status pipewire.socket pipewire-pulse.socket wireplumber.service
wpctl status
```

These are real, local systemd enablement links managed by systemd, not copied
user dotfiles. To choose the same default for every user, root may instead use
`systemctl --global enable pipewire.service pipewire-pulse.socket wireplumber.service`;
activate and verify the units from each normal user login. No lingering is needed.

Enable `pipewire.service` at user login; its unit also enables `pipewire.socket`.
Enabling only the sockets delays PipeWire and WirePlumber initialization until
the first client connects. On thinktop this produced an empty first
`wpctl status` and a mic LED transition when audio initialized. Starting the
service at login avoids that client-triggered startup, though device discovery
is still asynchronous. The LED before user login is kernel/firmware behavior.

If inspection finds an existing PulseAudio daemon or pipewire-media-session,
review and disable that user's competing units before starting the new stack.
Do not run PipeWire or WirePlumber as system services. Gentoo's `sound-server`
USE installs its WirePlumber audio enabler and supplies pipewire-pulse, the
PulseAudio protocol server; `pulseaudio` USE supplies libpulse integration.
ALSA clients use PipeWire through `pipewire-alsa`. Do not install a second audio
server or add an autostart launcher alongside systemd.

`@gui-base` also includes `media-sound/alsa-utils` for alsactl's privileged
ALSA/UCM initialization and mixer-state handling, plus diagnostic tools. This
is separate from the PipeWire audio server. UCM boot sequences can associate
hardware mute LEDs with ALSA controls through root-only sysfs attributes;
user-session WirePlumber alone cannot perform those writes. On thinktop,
manually applying the installed UCM's speaker LED associations restored F1 LED
tracking. After installing alsa-utils and rebooting, the user confirmed automatic
F1 LED tracking; the packaged startup path attached the amplifier controls without
the manual script. Verify this on other targets before adding custom LED
workarounds. Inspect `alsa-restore.service`, `alsa-state.service` and the packaged
udev rules rather than enabling both state-management schemes blindly.

### Check services and devices

Run all audio commands below as the normal desktop user inside Kitty, without
sudo. Check socket activation, running services, and device discovery:

```sh
systemctl --user status pipewire.socket pipewire-pulse.socket wireplumber.service
wpctl status
pactl info
systemctl --user status pipewire.service pipewire-pulse.service
pactl list short sinks
pactl list short sources
```

The sockets should be listening and WirePlumber running. After the clients have
connected, both PipeWire services should be running. `pactl info` should identify
the server as `PulseAudio (on PipeWire ...)`, confirming that these PulseAudio
clients use PipeWire. In `wpctl status`, check that the desired playback sink and
microphone source exist and have the default marker (`*`). A source named
`*.monitor` records speaker output rather than the physical microphone.

If the wrong device is selected, use the numeric **sink/source node IDs** shown
by `wpctl status`, rather than the card/device IDs. Replace these placeholders:

```sh
wpctl set-default <sink-node-id>
wpctl set-default <microphone-node-id>
```

Check mute and volume before playback or recording:

```sh
wpctl get-volume @DEFAULT_AUDIO_SINK@
wpctl get-volume @DEFAULT_AUDIO_SOURCE@
```

If muted, unmute the intended device. Start playback at a modest level and
adjust microphone gain as needed:

```sh
wpctl set-mute @DEFAULT_AUDIO_SINK@ 0
wpctl set-volume @DEFAULT_AUDIO_SINK@ 25%
wpctl set-mute @DEFAULT_AUDIO_SOURCE@ 0
```

### Test speakers, microphone, and controls

The installed freedesktop channel-announcement samples are **mono**, despite
living under `stereo/`. Plain playback normally sends them to both speakers.
Route each explicitly without upmixing for a browser-free channel test:

```sh
paplay --channel-map=front-left --no-remix /usr/share/sounds/freedesktop/stereo/audio-channel-front-left.oga
paplay --channel-map=front-right --no-remix /usr/share/sounds/freedesktop/stereo/audio-channel-front-right.oga
```

Confirm audible playback from the expected left/right speakers or headphones.
Speak into the microphone while this command records, then press Ctrl+C:

```sh
parec --device=@DEFAULT_SOURCE@ --file-format=wav /tmp/mic-test.wav
```

Replay the recording and confirm your speech is audible and clear:

```sh
paplay /tmp/mic-test.wav
```

Try the Hyprland volume-up/down, speaker-mute, and microphone-mute keys. Check
the resulting levels with `wpctl get-volume` and unmute before further tests.
These playback/recording commands exercise PulseAudio compatibility through
PipeWire. Native `pw-play`/`pw-record` require PipeWire's optional `extra` USE flag,
which this base does not enable.

For the separate ALSA compatibility check, use `aplay` if available:

```sh
aplay -L
aplay -D default /tmp/mic-test.wav
```

Confirm the default ALSA device uses the installed PipeWire ALSA configuration
and your recording plays. Avoid `-D hw:...`, which bypasses the compatibility
path. If `aplay` is absent on an installation predating the updated `@gui-base`,
install `media-sound/alsa-utils` as root with
`emerge --ask media-sound/alsa-utils`, then run the tests as the normal user.

### Check recovery and diagnose failures

After each manual or lid-triggered suspend/resume, repeat `wpctl status`, the
speaker test, and microphone record/replay. Verify that the intended devices
return and controls still work. Also verify startup after a fresh normal login.
Record the results in the open card; hearing a startup sound alone does not
establish microphone or resume correctness.

For connection failures, inspect the user services and session checks above.
For missing devices, inspect ALSA discovery and user-service logs:

```sh
cat /proc/asound/cards
journalctl --user -b -u pipewire.service -u pipewire-pulse.service -u wireplumber.service
```

If the kernel exposes no expected card, check audio driver/firmware errors as
root with `journalctl -k -b`, including SOF firmware on thinktop. If devices
exist but sound is absent, check default node selection, mute, volume, and the
selected profile/route before changing configuration. Preserve the relevant
output when reporting a failure.

Warnings from `mod.rt` reporting RTKit `ServiceUnknown` mean the optional
real-time scheduling service is unavailable. They do not indicate broken device
discovery or explain channel mixing. PipeWire can use process resource limits,
the realtime portal, or RTKit to obtain real-time scheduling; these warnings
alone do not establish the server threads' scheduling policy. If audio is stable,
record the limitation and continue testing. If playback/recording drops out under
load, inspect scheduling and consider Gentoo's optional `sys-auth/rtkit` package
after reviewing its dependency plan. Avoid adding services just to silence a
short-lived `wpctl` client's warnings. See the
[PipeWire realtime module documentation](https://docs.pipewire.org/page_module_rt.html).

