# Terminal secrets provisioning

## QEMU GitHub token

The tracked `/etc/agentoo/secrets/qemu.conf` selects the Login item
`agentoo/qemu-agentoo-github-token`. Its Username is your GitHub username and
Password is your repository-scoped personal access token. Run:

```sh
sudo agentoo-secrets --profile /etc/agentoo/secrets/qemu.conf --user graham github
```

The `github` method writes a root-owned mode `0600` credential file at
`/var/lib/agentoo/secrets/github.credentials`, then configures the installed
agentoo repository to use Git's built-in plaintext credential store for that
repository's HTTPS URL. It sets an HTTPS push URL without changing the fetch
URL. No custom helper or PIN prompt is installed. `agentoo-git push` can then
use the token. This command does not perform a push.

## Other file profiles

Run after creating the destination user and installing Proton Pass CLI.
Connectivity must already work. This script only installs files; it does not
start SSH agents, network services, or applications, and does not store items
back into the vault.

For a new local profile, copy `profile.example` to `/etc/agentoo/secrets/local.conf`.
Edit it to match your vault and destination files. Use a separate profile
for each host. The profile is plain data, not executable shell configuration.
The caller explicitly chooses the host profile; no host is inferred.

Each row means: install this vault field (or rendered template) at this path.
`HOME/` expands to the selected user's home. `user` makes the file owned by that
user; `root` makes it root-owned. All installed files have mode `0600`.
Parent directories are created or assigned mode `0700` for user destinations
and `0755` for root destinations. Choose dedicated parent directories.
Destination paths cannot contain whitespace; source references may.

For example, the SSH row retrieves the `private key` field and writes it to
`~/.ssh/id_ed25519`. The GitHub row writes only a token to a private file; it
does not configure Git or GitHub CLI to consume it. The Wi-Fi row expects an
entire native configuration stored in a note; change `wlan0` to your interface.
The Pi row is commented out until you supply a template matching your installed
Pi version. References can use IDs instead of names to avoid duplicate names.

```sh
sudo agentoo-secrets --profile /etc/agentoo/secrets/qemu.conf --user graham ssh github
```

Use `all` instead of category names to install every row. The script displays
destinations and asks once before logging in. It uses `login --interactive`,
including terminal password and TOTP prompts. Selected files are overwritten,
including `authorized_keys` if you add such a row; there is no append or merge.

Templates contain `{{ pass://vault/item/field }}` expressions. Proton performs
text substitution, not JSON or shell escaping. Make the template and stored
values appropriate for the destination format. No format-specific validation
is performed by this first version.

Each invocation uses a private `/run` directory and the CLI filesystem key
provider, keeping the temporary session and its key together in memory-backed
storage. It neither reuses nor logs out your ordinary CLI session. Exit cleanup
logs out and removes the directory, including on command failure or interruption.
SIGKILL or power loss cannot run cleanup; `/run` is cleared on reboot. Installed
files remain on disk and in local checkpoints. Partial installs are possible:
fix the failed reference and rerun. Avoid shell tracing (`bash -x`).

The QEMU profile is tracked configuration containing only references, not secret
values; pulling agentoo installs it directly under `/etc/agentoo/secrets/`.
Other profiles and templates there, the example GitHub token directory, and Pi
agent credential files are excluded by agentoo's Git ignore policy and remain
local configuration. Never put secret values in the tracked profile.
The script expects a trusted profile
and trusted destination paths; it is deliberately not a general hardened
deployment engine.
