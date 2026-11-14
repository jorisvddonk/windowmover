#!/usr/bin/env sh
set -eu

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
bin_dir="${XDG_BIN_HOME:-$HOME/.local/bin}"
app_dir="${XDG_DATA_HOME:-$HOME/.local/share}/applications"

mkdir -p "$bin_dir" "$app_dir"

for script in windowmover windowmover-tui windowmover-gui; do
    chmod +x "$repo_dir/scripts/$script"
    ln -sf "$repo_dir/scripts/$script" "$bin_dir/$script"
done

for entry in "$repo_dir"/desktop/*.desktop; do
    ln -sf "$entry" "$app_dir/$(basename "$entry")"
done

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$app_dir" >/dev/null 2>&1 || true
fi

printf 'Installed:\n'
printf '  %s/windowmover\n' "$bin_dir"
printf '  %s/windowmover-tui\n' "$bin_dir"
printf '  %s/windowmover-gui\n' "$bin_dir"
printf 'Desktop entries: %s\n' "$app_dir"
printf '\nTry: windowmover list\n'
