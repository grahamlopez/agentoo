# Repository status and terminal colors

## Repository status

`agentoo repos` checks the deployed system Agentoo repository
(`/var/lib/agentoo/repository.git` with `/` as its work tree), configured bare
work-tree pairs, and repositories throughout the invoking user's home.
A missing system deployment is normal when working from a checkout. For an
existing deployment, non-root users are asked for sudo authorization for the
system check. Only that fixed repository/work-tree pair runs as root; the home
scan and user repositories continue under the invoking account. The command does
not change permissions or Git's safe-directory policy.

If you decline authentication or cancel its prompt with Ctrl+C, the system
repository is reported as unavailable and the home checks continue. Exit 1
signals the incomplete check. `--no-input` prevents sudo and fetch password prompts: it uses
cached sudo authorization when available, otherwise reports the system check
unavailable. Help and explicit `--path` scans never request sudo. Running the
entire command under sudo yourself changes the invoking account and normally its
home; ordinary use does not require that.

```sh
agentoo repos
agentoo repos --path=.
agentoo repos --path=~/work --path=~/projects
agentoo repos --exclude='Synct' --exclude='*/plugins/*'
agentoo repos --path=. --fetch
agentoo repos --json
agentoo repos --no-input --json
```

Supplying any `--path` replaces the default scope: it scans only the selected
paths, omitting the special system and configured-pair checks. Bare repositories
with `core.worktree` inside those paths are still discovered. Hidden directories
are included. Directory symlinks are not followed; explicitly supplied symlink
roots are resolved. Nested repositories and linked worktrees are included, with
duplicate Git-directory/work-tree pairs reported only once. The scan prunes
`.git`, `.cache`, `node_modules`, `.venv`, `__pycache__`, `.Trash`, and `Trash`.
Pure bare repositories without a work tree are skipped.

An aligned table shows the work-tree path, branch (or detached commit), staged,
modified, untracked, and unmerged counts, plus upstream ahead/behind counts.
A file can count as both staged and modified. Untracked directories count as
one entry, following Git's normal status behavior. Missing upstream configuration
and an upstream whose reference is unavailable are distinguished. Without
`--fetch`, ahead/behind counts use existing local remote-tracking references.
Paths under your home are shortened to `~`; the system entry is labeled
`system Agentoo (/)`. Changes and missing upstreams are yellow, commits ahead
are cyan, and conflicts, divergence, unavailable status, and fetch failures are
red. Clean/synchronized states use normal text. Color is enabled only on a TTY,
with `TERM` other than `dumb` and `NO_COLOR` unset. JSON remains uncolored.

For system and bare work-tree pairs, status checks **tracked files only**.
Untracked counts are unavailable, rather than zero: checking untracked files
across `/` or a home work tree would be costly and noisy. Ordinary repositories
include untracked entries. Git's optional index-refresh writes are disabled.

`--fetch` explicitly fetches all remotes before status. Normal fetches use your
Git/SSH configuration and can prompt for key passphrases, credentials, and host
confirmation. Fetch diagnostics and prompts go directly to stderr, keeping JSON
on stdout valid. Interactive fetches have no deadline while authentication may
be waiting for you. `--no-input` disables Git credential prompts, selects SSH
batch mode, disconnects stdin, and limits each fetch to 60 seconds. This mode
uses standard SSH instead of a custom SSH command, and requires existing
credentials and previously configured hosts. Status has a 15-second timeout.
Fetch failures do not suppress local status. The command never resets, checks
out, stages, commits, or pushes.
System fetching runs as root after sudo authorization, so it uses root's Git/SSH
credentials; user repository fetching retains the invoking user's credentials.

### Local configuration

Optional configuration lives in `$XDG_CONFIG_HOME/agentoo/repos.json`, defaulting
to `~/.config/agentoo/repos.json`. Use `--config FILE` to select another file.
The file remains local and is not installed or tracked by Agentoo.

```json
{
  "exclude": ["Synct", "*/.claude/plugins/*"],
  "repositories": [
    {"git_dir": "~/.dots-git", "work_tree": "~"}
  ]
}
```

Repository paths must be absolute or start with `~`. These pairs supplement the
default scope and always check tracked files only. Bare repositories discovered
under home with their own `core.worktree` need no explicit entry. Exclusions
match directory names, absolute paths, or paths relative to each scan root,
using shell-style glob patterns. Matching directories are pruned with all their
contents. Explicit scan roots and explicit pairs are not excluded.

### Machine output and exit status

`--json` emits one object with `repositories` and `errors` arrays. Successful
repository records contain `git_dir`, `work_tree`, `branch`, `oid`, `upstream`,
`ahead`, `behind`, `staged`, `modified`, `untracked`, `unmerged`, `tracked_only`,
`error`, and `fetch_error`. Unavailable upstream/count data is `null`. Unborn
branches have `oid: "(initial)"`; detached branches have `branch: "(detached)"`.
Failed status records contain the paths, `error`, and `fetch_error`; do not treat
missing counts as clean. Scan errors have `path` and `error`. Diagnostics also go
to stderr. Ordering is by work-tree path, then Git-directory path.

Exit 0 means all checks succeeded, including dirty, diverged, or empty results;
1 means a scan, status, or fetch failed; 2 means invalid arguments/configuration.
No network operations occur without `--fetch`.

## Terminal color visual tests

Run `agentoo term-colors` in a terminal, then repeat inside tmux and over SSH to
compare the rendering. The command prints:

- The 16 ANSI colors with normal and bold text against the default background.
- Normal/bold foreground/background combinations for the eight base colors.
- All 256 indexed colors in nine-column-wide, two-line swatches: slot above hex.
  Labels use whichever of true black or white has greater contrast with the
  standard background. Hex labels cover xterm colors 16–255; slots 0–15 are
  labeled theme-defined, with contrast estimated from conventional ANSI colors.
- A grayscale strip and 24-bit red, green, blue, gray, and spectrum gradients.
- Hex → decimal RGB → truecolor examples, plus hex endpoints on each gradient.

Look for unreadable palette colors, indistinguishable shades, or unexpectedly
stepped RGB gradients. ANSI palette colors depend on the selected terminal
theme. The tool emits samples directly, without external commands or automatic
pass/fail judgments. It does not diagnose font coverage or change the palette.
Hex labels on indexed swatches describe the standard xterm palette; a customized
terminal palette can redefine these slots. Truecolor examples request the RGB
values directly rather than looking up a palette slot.

Chart columns adapt to terminal width; very narrow terminals can still wrap
labels or individual swatches. Every swatch or gradient row resets styling, and
completion/interruption attempts a final reset to terminal defaults. It does not
restore arbitrary styling that was active before invocation.

Redirection, `TERM=dumb`, and `NO_COLOR` require explicit `--force`:

```sh
agentoo term-colors --force > color-samples.ansi
```

Exit 0 means output completed; 2 means invalid arguments or an output restriction.
Broken pipes return 1 and interruption returns 130. Output contains terminal
escape sequences, so the redirected file is intended for terminal replay.
