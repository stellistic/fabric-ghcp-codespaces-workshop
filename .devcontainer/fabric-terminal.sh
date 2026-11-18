#!/usr/bin/env bash
set -euo pipefail
umask 077

if [[ -z "${DBUS_SESSION_BUS_ADDRESS:-}" ]]; then
    exec dbus-run-session -- bash "$0"
fi

read -r -s -p 'Create/unlock the encrypted Fabric keyring (nonempty password, not a token): ' keyring_password
printf '\n'
if [[ -z "$keyring_password" ]]; then
    printf '%s\n' 'A nonempty keyring password is required; encryption is never disabled.' >&2
    exit 1
fi
printf '%s' "$keyring_password" | gnome-keyring-daemon --unlock --components=secrets >/dev/null
unset keyring_password
printf '%s\n' 'Encrypted keyring session started. Login and run Fabric commands only in this shell.'
exec bash
