#!/bin/bash
# Run after 001-firstboot-verify-and-checkpoint.sh on the booted target.
# Passwords and authorized keys are local state, never repository payload.
set -Eeuo pipefail
umask 077
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
case ${1:-} in
  --help|-h) printf 'Usage: %s\nCreate/validate graham, prompt for a password and optional SSH login key.\n' "$0"; exit 0 ;;
  '') (( $# == 0 )) || die 'No arguments supported.' ;;
  *) die 'Only --help is supported.' ;;
esac
(( EUID == 0 )) || die 'Run as root.'
[[ -r /etc/gentoo-release && -d /run/systemd/system ]] || die 'Run on the booted Gentoo target, not in a chroot.'
[[ -t 0 && -t 1 ]] || die 'An interactive terminal is required.'
exec 9>/run/agentoo-setup-user.lock
flock -n 9 || die 'Another user setup is running.'
account=graham
home=/home/graham
uid=1000
gid=1000
policy=/etc/sudoers.d/90-agentoo-graham
validate_identity() {
  local record actual_uid actual_gid actual_home shell
  record=$(getent passwd "$account" || true)
  if [[ -n $record ]]; then
    IFS=: read -r _ _ actual_uid actual_gid _ actual_home shell <<< "$record"
    [[ $actual_uid == "$uid" && $actual_gid == "$gid" && $actual_home == "$home" ]] || die 'Existing graham identity conflicts with UID/GID 1000 and /home/graham.'
  else
    ! getent passwd "$uid" >/dev/null || die 'UID 1000 belongs to another account.'
    [[ ! -e $home && ! -L $home ]] || die 'Home exists without the expected account; inspect it first.'
  fi
  record=$(getent group "$account" || true)
  if [[ -n $record ]]; then
    [[ $(cut -d: -f3 <<< "$record") == "$gid" ]] || die 'Group graham has a conflicting GID.'
  else
    ! getent group "$gid" >/dev/null || die 'GID 1000 belongs to another group.'
  fi
  getent group wheel >/dev/null || die 'Required wheel group is missing.'
  getent group portage >/dev/null || die 'Required portage group is missing.'
  if [[ -e $home || -L $home ]]; then
    [[ -d $home && ! -L $home && $(stat -c %u "$home") == "$uid" ]] || die 'Home must be a real directory owned by graham.'
  fi
}
validate_identity
printf '\n┌─ User setup ─────────────────────────────────────┐\n'
printf '│ Account       graham · UID/GID 1000:1000\n│ Home          /home/graham · no skeleton dotfiles\n│ Groups        graham (primary), wheel, portage\n│ Shell         Zsh\n│ Console       Account password (prompted below)\n│ Sudo          Account password required\n│ SSH           Optional public key; key-only login for Graham\n│ Git identity  Optional one-time setup; interrupted runs resume\n│ Packages      Zsh, sudo, OpenSSH, Git\n└──────────────────────────────────────────────────┘\n'
read -r -p 'Proceed with user setup? [y/N] ' answer
[[ $answer == y || $answer == Y || $answer == yes ]] || { echo 'User setup declined; no account or package changes made.'; exit 0; }
printf '\nPaste one SSH public key (empty to skip). Label: agentoo:graham:ssh-login\n'
read -r -p 'SSH public key: ' public_key
packages=(app-shells/zsh app-admin/sudo net-misc/openssh dev-vcs/git)
# Show Portage's dependency/build plan and obtain its own confirmation.
emerge --ask --noreplace "${packages[@]}"
shell=$(readlink -f "$(command -v zsh)") || die 'Zsh is unavailable.'
grep -Fxq "$shell" /etc/shells || die 'Installed Zsh is not listed in /etc/shells.'
[[ -f /etc/ssh/sshd_config.d/10-agentoo-graham.conf && ! -L /etc/ssh/sshd_config.d/10-agentoo-graham.conf ]] || die 'Managed SSH policy is missing; update the agentoo checkout.'
# Generate missing server host keys without starting the service.
ssh-keygen -A
sshd -t || die 'SSH configuration is invalid.'
ssh_config=$(sshd -T -C user=graham,host=localhost,addr=127.0.0.1)
for setting in 'passwordauthentication no' 'kbdinteractiveauthentication no'; do
  grep -Fxiq "$setting" <<< "$ssh_config" || die 'SSH configuration conflicts with key-only access for Graham.'
done
visudo -c || die 'Existing sudo configuration is invalid.'
[[ -f $policy && ! -L $policy ]] || die 'Managed sudo policy is missing; update the agentoo checkout.'
visudo -cf "$policy" || die 'Managed sudo policy is invalid.'
key_file=$(mktemp)
trap 'rm -f "$key_file"' EXIT
if [[ -n $public_key ]]; then
  # Authorized-key options are intentionally unsupported at this prompt.
  read -r key_type key_data key_comment <<< "$public_key"
  [[ $key_type == ssh-* || $key_type == ecdsa-* || $key_type == sk-* ]] || die 'Paste a plain public key, without authorized_keys options.'
  [[ -n $key_data ]] || die 'Missing SSH key data.'
  printf '%s %s agentoo:graham:ssh-login%s\n' "$key_type" "$key_data" "${key_comment:+ $key_comment}" > "$key_file"
  ssh-keygen -lf "$key_file" >/dev/null || die 'Invalid SSH public key; no account changes made.'
fi
validate_identity
getent group "$account" >/dev/null || groupadd --gid "$gid" "$account"
if ! getent passwd "$account" >/dev/null; then
  useradd --uid "$uid" --gid "$account" --groups wheel,portage --shell "$shell" --home-dir "$home" --no-create-home "$account"
  install -d -m 0700 -o "$uid" -g "$gid" "$home"
else
  # Preserve existing supplementary groups and home contents on subsequent runs.
  usermod --append --groups wheel,portage --shell "$shell" "$account"
  [[ -d $home ]] || install -d -m 0700 -o "$uid" -g "$gid" "$home"
fi
password_status=$(passwd -S "$account")
read -r _ password_status _ <<< "$password_status"
if [[ $password_status != P ]]; then
  printf '\nSet Graham’s account password (also used by sudo):\n'
  passwd "$account"
else
  printf '\nExisting account password preserved.\n'
fi
# Mark the optional choice only after completion, so interrupted setup can resume.
identity_done=/var/lib/agentoo/graham-git-identity.done
identity_file=$home/.gitconfig-local
if [[ ! -e $identity_done ]]; then
  git_name="graham (@$(hostname))"
  git_email='m477@duck.com'
  printf '\n┌─ Personal Git identity ──────────────────────────┐\n'
  printf '│ Author name   %s\n│ Author email  %s\n│ Storage       ~/.gitconfig-local (Graham only)\n└──────────────────────────────────────────────────┘\n' "$git_name" "$git_email"
  read -r -p 'Configure Git identity? [y/N] ' answer
  if [[ $answer == y || $answer == Y || $answer == yes ]]; then
    read -r -p "Author name [$git_name]: " value
    git_name=${value:-$git_name}
    read -r -p "Author email [$git_email]: " value
    git_email=${value:-$git_email}
    [[ ! -L $identity_file && ( ! -e $identity_file || ( -f $identity_file && $(stat -c %u "$identity_file") == "$uid" ) ) ]] || die 'Git identity file must be a regular file owned by Graham.'
    # runuser retains root's working directory; Git must start in Graham's home.
    for field in name email; do
      identity_variable=git_$field
      value=$(runuser -u "$account" -- git -C "$home" config --file "$identity_file" --get "user.$field" || true)
      [[ -n $value ]] || runuser -u "$account" -- git -C "$home" config --file "$identity_file" "user.$field" "${!identity_variable}"
    done
  else
    printf '\nGit identity skipped. Later, run these as Graham (edit the values as needed):\n'
    printf '  git config --file "$HOME/.gitconfig-local" user.name %q\n' "$git_name"
    printf '  git config --file "$HOME/.gitconfig-local" user.email %q\n' "$git_email"
  fi
  touch "$identity_done"
fi
# Apply Graham’s key-only policy to an already-running server; do not start it.
if systemctl is-active --quiet sshd.service; then systemctl reload sshd.service; fi
ssh_status='No key added; password authentication disabled'
if [[ -n $public_key ]]; then
  ssh_dir=$home/.ssh
  authorized=$ssh_dir/authorized_keys
  [[ ! -L $ssh_dir && ( ! -e $ssh_dir || -d $ssh_dir ) ]] || die 'Unsafe .ssh path.'
  [[ ! -L $authorized && ( ! -e $authorized || -f $authorized ) ]] || die 'Unsafe authorized_keys path.'
  [[ ! -e $ssh_dir || $(stat -c %u "$ssh_dir") == "$uid" ]] || die '.ssh must be owned by graham.'
  [[ ! -e $authorized || $(stat -c %u "$authorized") == "$uid" ]] || die 'authorized_keys must be owned by graham.'
  [[ ! -e $authorized || $(stat -c %h "$authorized") == 1 ]] || die 'Hard-linked authorized_keys is unsupported.'
  install -d -m 0700 -o "$uid" -g "$gid" "$ssh_dir"
  touch "$authorized"
  # Identify duplicates by key material, not by their descriptive comments.
  if ! awk -v type="$key_type" -v data="$key_data" '{for(i=1;i<NF;i++) if($i==type && $(i+1)==data) found=1} END {exit !found}' "$authorized"; then
    [[ ! -s $authorized ]] || printf '\n' >> "$authorized"
    cat "$key_file" >> "$authorized"
  fi
  chown "$uid:$gid" "$authorized"
  chmod 0600 "$authorized"
  ssh_status='Login key authorized; password authentication disabled'
fi
visudo -c
sudo -l -U "$account"
printf '\n┌─ User setup complete ─────────────────────────────┐\n│ Console login  Account password\n│ Sudo           Account password required\n│ SSH login      %s\n└──────────────────────────────────────────────────┘\n' "$ssh_status"
printf '\nTest a new Graham login, then run: sudo -k; sudo -i\nKeep your root console open until that succeeds.\n'
