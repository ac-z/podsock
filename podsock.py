#!/usr/bin/env python3

# Podsock - podman wrapper with +flags
# Copyright (C) 2026 Amber Connelly
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Podsock - podman wrapper with +flags.
"""

import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import time


__version__ = "0.1.0"

PODSOCK_INIT = os.environ.get("PODSOCK_INIT", "1")
PODSOCK_RTDIR = os.environ.get("PODSOCK_RTDIR", f"/run/user/{os.getuid()}")

_BOOL_LONG_OPTS = frozenset(["--help", "--version", "--syslog"])
_GLOBAL_SHORT_VAL_OPTS = frozenset("cH")
_FLAG_DESCS = {
    "t": "Terminal interactivity (uses $TERM)",
    "T": "Terminal interactivity (forces xterm-256color)",
    "w": "Wayland display forwarding",
    "s": "SSH agent socket forwarding",
    "g": "GPU/graphics device access",
    "p": "PipeWire playback-only audio forwarding",
    "P": "PipeWire full audio forwarding",
    "n": "Host network with extra capabilities",
    "d": "Debug capabilities (ptrace, perfmon)",
    "A": "Register as desktop app (creates .desktop launcher)",
    "D": "Enable XDG Desktop Portal access (implies +A, filtered D-Bus)",
    "f": "FUSE filesystem support (e.g. sshfs)",
    "?": "Dry run (print command without executing)",
}
_ALLOWED_FLAGS = {"run": "tTwsgpPndADf?", "create": "tTwsgpPndADf?"}


def die(msg):
    """Print message to stderr and exit with code 1."""
    print(msg, file=sys.stderr)
    sys.exit(1)


def show_help(subcommand=None):
    """Display podman help followed by podsock-specific help.

    Podman's help output is shown first so that podsock's own additions
    (flags, examples, warnings) appear at the bottom of the terminal and
    remain visible without scrolling.
    """
    # Special cases that don't delegate to podman
    if subcommand == "help":
        print("Show help for a podsock command.")
        print("Usage: podsock help <command>")
        return
    if subcommand == "cleanup":
        print("Clean up stale D-Bus proxies and .desktop files for deleted containers.")
        print("Usage: podsock cleanup")
        print()
        print("Scans all containers with podsock labels. Running containers are left untouched.")
        print("Stopped containers have their proxy stopped. Fully removed (orphan) containers")
        print("have both their proxy directories and .desktop files cleaned up.")
        return

    # Determine available flags
    if subcommand in _ALLOWED_FLAGS:
        flags = list(_ALLOWED_FLAGS[subcommand])
    elif subcommand in ("shell", "helm"):
        flags = ["?"]
    else:
        flags = ["?"] if subcommand else []

    podman_cmd = {"shell": "exec", "helm": "start"}.get(subcommand, subcommand)
    podman_bin = shutil.which("podman")

    # Run podman help first — its output is long and will scroll off the top,
    # leaving podsock's own help visible at the bottom of the terminal.
    if subcommand:
        print(f"--- Podman help for '{podman_cmd}' ---")
        if podman_bin:
            subprocess.run([podman_bin, podman_cmd, "--help"], check=False)
        else:
            print("Error: podman not found in PATH", file=sys.stderr)
    else:
        print("--- Podman help ---")
        if podman_bin:
            subprocess.run([podman_bin, "--help"], check=False)
        else:
            print("Error: podman not found in PATH", file=sys.stderr)

    print()
    print("--- Podsock ---")
    print("Podsock - podman wrapper with +flags")
    print()
    print("Usage: podsock [+flags] <command> [args...]")
    print()

    if subcommand:
        print(f"Available +flags for '{subcommand}':")
        for f in flags:
            print(f"  +{f}  {_FLAG_DESCS[f]}")
        print()
    else:
        print("Subcommands:")
        print("  shell <container> [command]  Run a shell (or command) in a running container")
        print("  helm <container>             Start a container interactively")
        print("  cleanup                      Clean up stale D-Bus proxies and .desktop files")
        print()
        print("Available +flags (all commands):")
        print("  +?  Dry run (print command without executing)")
        print()

    # Examples
    print("Examples:")
    if subcommand in ("run", "create"):
        print("  podsock run +Twg --rm -it ubuntu bash    Terminal + Wayland + GPU")
        print("  podsock run +p --rm -it myimage          Playback-only audio")
        print("  podsock run +D --name=myapp myimage      Desktop portal access")
        print("  podsock +? run +Tngd myimage             Dry run (print podman command)")
    elif subcommand in ("shell", "helm"):
        print(f"  podsock {subcommand} mycontainer")
        print(f"  podsock +? {subcommand} mycontainer       Dry run")
    else:
        print("  podsock run +Twg --rm -it ubuntu bash    Terminal + Wayland + GPU")
        print("  podsock shell mycontainer                Shell into running container")
        print("  podsock helm mycontainer                 Start container interactively")
        print("  podsock cleanup                          Clean up stale proxies")
        print("  podsock +? run +Tngd myimage             Dry run (print podman command)")
    print()

    if subcommand in ("run", "create"):
        print(
            "WARNING: +D does NOT filter individual portal interfaces. Access control is\n"
            "delegated to the desktop environment's permission dialogs. Treat untrusted\n"
            "apps with the same caution as a Flatpak with full portal access."
        )
        print()

    if not subcommand:
        print("Use 'podsock <command> --help' for command-specific help.")
        print("Full documentation: man podsock")


def print_bash_completion():
    """Print a bash completion script for podsock."""
    print(r"""_podsock() {
    local cur="${COMP_WORDS[COMP_CWORD]}"
    local i subcmd=""

    # Detect subcommand for +flags
    for ((i=1; i<COMP_CWORD; i++)); do
        case "${COMP_WORDS[i]}" in
            run|create) subcmd="${COMP_WORDS[i]}"; break ;;
            shell|helm) subcmd="${COMP_WORDS[i]}"; break ;;
        esac
    done

    # Complete +flags (chainable, e.g. +Tdnws?)
    if [[ "$cur" == +* ]]; then
        local avail=""
        case "$subcmd" in
            run|create) avail="tTwsgpPndADf?" ;;
            shell|helm) avail="?" ;;
            *) avail="?" ;;
        esac

        local used=""
        for ((i=1; i<=COMP_CWORD; i++)); do
            local w="${COMP_WORDS[i]}"
            [[ "$w" == +* ]] && used="${used}${w:1}"
        done

        local remaining=""
        for ((i=0; i<${#avail}; i++)); do
            local c="${avail:$i:1}"
            [[ "$used" == *"$c"* ]] && continue
            # +t and +T are mutually exclusive (different terminal modes)
            [[ "$c" == "t" && "$used" == *T* ]] && continue
            [[ "$c" == "T" && "$used" == *t* ]] && continue
            remaining="${remaining}${c}"
        done

        COMPREPLY=()
        for ((i=0; i<${#remaining}; i++)); do
            COMPREPLY+=("${cur}${remaining:$i:1}")
        done
        return 0
    fi

    # Build podman-equivalent args array (strip +flags, map subcommands)
    local podman_args=()
    local found=0
    for ((i=1; i<COMP_CWORD; i++)); do
        local w="${COMP_WORDS[i]}"
        [[ "$w" == +* ]] && continue
        if [[ $found -eq 0 ]]; then
            case "$w" in
                shell) w="exec" ;;
                helm)  w="start" ;;
            esac
            found=1
        fi
        podman_args+=("$w")
    done

    # Include current word if non-empty
    if [[ -n "$cur" ]]; then
        podman_args+=("$cur")
    fi

    # Cobra expects an empty arg when the cursor is at a word boundary
    local lastParam="${COMP_WORDS[COMP_CWORD]}"
    local lastChar=${lastParam:$((${#lastParam}-1)):1}

    local out
    if [[ -z "$cur" && "$lastChar" != "=" ]]; then
        out=$(podman __complete "${podman_args[@]}" '' 2>/dev/null)
    else
        out=$(podman __complete "${podman_args[@]}" 2>/dev/null)
    fi

    # Handle flag-with-value completions (e.g. --name=myi<TAB>)
    local cur_prefix=""
    if [[ "$cur" == -*=* ]]; then
        cur_prefix="${cur%%=*}="
        cur="${cur#*=}"
    fi

    if [[ -z "$out" ]]; then
        return
    fi

    # Extract Cobra directive (bitmask after the last colon)
    local directive="${out##*:}"
    local completions="${out%:*}"
    if [[ "$directive" == "$out" ]]; then
        directive=0
    fi

    # Parse completions into COMPREPLY
    local tab=$'\t'
    local comp val
    while IFS= read -r comp; do
        [[ -z "$comp" ]] && continue
        # Skip activeHelp lines
        [[ "$comp" == _activeHelp_* ]] && continue
        # Strip description
        val="${comp%%$tab*}"
        # Strip flag prefix for =-style flag values
        if [[ -n "$cur_prefix" && "$val" == "$cur_prefix"* ]]; then
            val="${val#$cur_prefix}"
        fi
        COMPREPLY+=("$val")
    done <<<"$completions"

    # Detect if we're past the subcommand position (any non-flag word typed)
    local past_subcmd=0
    for ((i=1; i<COMP_CWORD; i++)); do
        local w="${COMP_WORDS[i]}"
        [[ "$w" == +* ]] && continue
        [[ "$w" == -* ]] && continue
        past_subcmd=1
        break
    done

    # Inject podsock-specific subcommands when at the subcommand position
    if [[ $past_subcmd -eq 0 && "$cur" != -* ]]; then
        while IFS= read -r line; do
            COMPREPLY+=("$line")
        done < <(compgen -W "shell helm cleanup" -- "$cur")
    fi

    # Apply Cobra directives
    local shellCompDirectiveNoSpace=2
    local shellCompDirectiveNoFileComp=4

    if (( (directive & shellCompDirectiveNoSpace) != 0 )); then
        if [[ $(type -t compopt) == builtin ]]; then
            compopt -o nospace
        fi
    fi
    if (( (directive & shellCompDirectiveNoFileComp) != 0 )); then
        if [[ $(type -t compopt) == builtin ]]; then
            compopt +o default
        fi
    fi
}

complete -o default -F _podsock "${BASH_SOURCE##*/}"
""")


# ---------------------------------------------------------------------------
# App ID / .desktop / proxy helpers
# ---------------------------------------------------------------------------

_DESKTOP_DIR = os.path.expanduser("~/.local/share/applications")


def _generate_app_id(name):
    """Generate a D-Bus app ID from a container name."""
    if name:
        # Replace all non-alphanumeric with underscore
        sanitized = re.sub(r"[^A-Za-z0-9]", "_", name)
        # Must start with a letter
        if sanitized and sanitized[0].isdigit():
            sanitized = "x" + sanitized
    else:
        # Unnamed container: 8-char hex
        sanitized = os.urandom(4).hex()
    app_id = f"podsock_{sanitized}"
    # D-Bus name limit is 255 chars
    return app_id[:255]


def _desktop_file_path(app_id):
    return os.path.join(_DESKTOP_DIR, f"{app_id}.desktop")


def _create_desktop_file(app_id, container_name, dryrun=False):
    """Idempotently create a .desktop launcher for the container."""
    path = _desktop_file_path(app_id)
    contents = (
        "[Desktop Entry]\n"
        f"Name=Podsock Container: {container_name}\n"
        f"Exec=podsock helm {container_name}\n"
        "Type=Application\n"
        "Icon=application-x-executable\n"
        "Terminal=true\n"
        "Categories=Development;\n"
    )
    if dryrun:
        return
    os.makedirs(_DESKTOP_DIR, exist_ok=True)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            if f.read() == contents:
                return
    with open(path, "w", encoding="utf-8") as f:
        f.write(contents)


def _delete_desktop_file(app_id):
    path = _desktop_file_path(app_id)
    if os.path.exists(path):
        os.unlink(path)


def _podsock_var_dir():
    """Return the base podsock var directory, creating it with 0o700 if needed."""
    path = os.path.expanduser("~/.var/podsock")
    if not os.path.isdir(path):
        os.makedirs(path, mode=0o700, exist_ok=True)
    return path


def _proxy_socket_dir(name):
    """Return the persistent host directory that holds the proxy socket."""
    return os.path.join(_podsock_var_dir(), "sockets", name)


def _proxy_socket_path(name):
    return os.path.join(_proxy_socket_dir(name), "bus.sock")


# ---------------------------------------------------------------------------
# Data file helpers
# ---------------------------------------------------------------------------

def _read_data_file(filename):
    """Read a podsock data file from standard locations."""
    # 1. Explicit override
    env_dir = os.environ.get("PODSOCK_DATADIR")
    if env_dir:
        path = os.path.join(env_dir, filename)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()

    # 2. Development: relative to this script
    dev_path = os.path.join(os.path.dirname(__file__), "share", filename)
    if os.path.exists(dev_path):
        with open(dev_path, "r", encoding="utf-8") as f:
            return f.read()

    # 3. Installed: relative to the running binary (standard prefix layout)
    bin_path = os.path.realpath(sys.argv[0])
    if os.path.isfile(bin_path):
        installed_path = os.path.join(os.path.dirname(bin_path), "..", "share", "podsock", filename)
        installed_path = os.path.normpath(installed_path)
        if os.path.exists(installed_path):
            with open(installed_path, "r", encoding="utf-8") as f:
                return f.read()

    # 4. Standard FHS data directories
    for prefix in ("/usr/local", "/usr"):
        path = os.path.join(prefix, "share", "podsock", filename)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()

    # 5. User-local
    path = os.path.join(os.path.expanduser("~/.local"), "share", "podsock", filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    die(f"Error: podsock data file not found: {filename}")


def _ensure_pipewire_playback_configs():
    """Write playback-only host-side configs if missing, after user consent.

    Returns True if config files were written, False if they already existed.
    """
    xdg = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    pw_dir = os.path.join(xdg, "pipewire", "pipewire.conf.d")
    wp_dir = os.path.join(xdg, "wireplumber", "wireplumber.conf.d")
    configs = [
        (pw_dir, "99-podsock-playback.conf", "pipewire-playback.conf"),
        (wp_dir, "99-podsock-playback-only.conf", "wireplumber-playback-only.conf"),
    ]

    pending = []
    for dir_path, dest_name, src_name in configs:
        path = os.path.join(dir_path, dest_name)
        if not os.path.exists(path):
            pending.append((dir_path, path, src_name))

    if not pending:
        return False

    print("\nWARNING: +p requires host-side PipeWire/WirePlumber configuration", file=sys.stderr)
    print("         files that modify your system's audio daemon. This affects", file=sys.stderr)
    print("         all PipeWire clients, not just this container.", file=sys.stderr)
    print("\n  The following files will be created:", file=sys.stderr)
    for _, path, src_name in pending:
        print(f"    {path}", file=sys.stderr)
    print("\n  After installation, you must restart PipeWire:", file=sys.stderr)
    print("    systemctl --user restart pipewire wireplumber", file=sys.stderr)
    print(file=sys.stderr)

    try:
        resp = input("Install these config files? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        resp = ""
    if resp not in ("y", "yes"):
        die("Aborted. No config files were written.")

    for dir_path, path, src_name in pending:
        os.makedirs(dir_path, exist_ok=True)
        print(f"Installing {src_name} to {path}", file=sys.stderr)
        contents = _read_data_file(src_name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(contents)

    return True


def _start_xdg_dbus_proxy(app_id, name, dryrun=False):
    """Start a filtered xdg-dbus-proxy; return socket path."""
    socket_dir = _proxy_socket_dir(name)
    socket_path = _proxy_socket_path(name)

    if dryrun:
        return socket_path

    # Reuse existing socket if already accepting connections
    if os.path.exists(socket_path):
        if not stat.S_ISSOCK(os.stat(socket_path).st_mode):
            die(f"Error: proxy socket path exists but is not a socket: {socket_path}")
        return socket_path

    os.makedirs(socket_dir, exist_ok=True)

    # Detect host session bus address
    dbus_addr = os.environ.get("DBUS_SESSION_BUS_ADDRESS", "")
    if not dbus_addr.startswith("unix:"):
        die("Error: DBUS_SESSION_BUS_ADDRESS is not a unix socket (required for +D)")

    proxy_bin = "xdg-dbus-proxy"
    # Verify xdg-dbus-proxy is in PATH and executable
    if not any(
        os.path.isfile(os.path.join(p, proxy_bin)) and os.access(os.path.join(p, proxy_bin), os.X_OK)
        for p in os.environ.get("PATH", "").split(":")
    ):
        die(f"Error: {proxy_bin} not found in PATH or not executable (required for +D)")

    # Arguments: ADDRESS PATH --filter --talk=... --talk=...
    proxy_args = [
        proxy_bin,
        dbus_addr,
        socket_path,
        "--filter",
        "--talk=org.freedesktop.portal.Desktop",
        "--talk=org.freedesktop.portal.Documents",
    ]

    # Try systemd-run first for per-container app ID tracking
    unit_name = f"app-{app_id}.service"
    systemd_run = ["systemd-run", "--user", f"--unit={unit_name}",
                   "--property=KillMode=process",
                   "--property=CollectMode=inactive-or-failed"] + proxy_args

    systemd_used = False
    try:
        # Check if unit is already active (idempotent restart)
        active = subprocess.run(
            ["systemctl", "--user", "is-active", unit_name],
            capture_output=True, check=False,
        )
        if active.returncode == 0:
            # Unit already running; poll for socket
            for _ in range(20):
                if os.path.exists(socket_path):
                    return socket_path
                time.sleep(0.05)
            die("Error: proxy unit is active but socket did not appear")
        subprocess.run(systemd_run, check=True, capture_output=True)
        systemd_used = True
    except FileNotFoundError:
        # systemd-run / systemctl not available
        print("WARNING: systemd user session unavailable; portal permissions will not be tracked per-container.",
              file=sys.stderr)
    except subprocess.CalledProcessError:
        # systemd-run failed for some reason; fallback
        print("WARNING: systemd-run failed; falling back to direct proxy. Portal permissions will not be tracked per-container.",
              file=sys.stderr)

    if not systemd_used:
        # Fallback: run proxy directly as a background subprocess
        proc = subprocess.Popen(proxy_args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Record PID for later cleanup
        pid_path = os.path.join(socket_dir, "proxy.pid")
        with open(pid_path, "w", encoding="utf-8") as f:
            f.write(str(proc.pid))

    # Poll for socket (systemd-run returns before socket is created)
    for _ in range(20):
        if os.path.exists(socket_path):
            break
        time.sleep(0.05)
    else:
        die("Error: xdg-dbus-proxy failed to create socket")

    return socket_path


def _cleanup_dbus():
    """Clean up stale D-Bus proxies and .desktop files for stopped containers."""
    # Get all containers with podsock labels
    try:
        out = subprocess.run(
            ["podman", "ps", "-a", "--filter", "label=podsock.app_id", "--format", "json"],
            capture_output=True, text=True, check=False,
        )
        containers = json.loads(out.stdout) if out.stdout.strip() else []
        if not isinstance(containers, list):
            containers = []
    except Exception as e:
        die(f"Error: failed to list podman containers: {e}")

    running = []
    stopped = []
    for c in containers:
        labels = c.get("Labels") or {}
        app_id = labels.get("podsock.app_id")
        name = labels.get("podsock.name") or (c.get("Names", [None])[0] if c.get("Names") else None) or c.get("Id")
        state = c.get("State", "").lower()
        if app_id and name:
            if state in ("running", "up", "paused", "restarting"):
                running.append((app_id, name))
            else:
                stopped.append((app_id, name))

    cleaned = 0

    # Clean up stopped containers: stop proxy (to save resources) but keep
    # the socket directory and .desktop file so the container can be restarted.
    for app_id, name in stopped:
        socket_dir = _proxy_socket_dir(name)
        if os.path.isdir(socket_dir):
            _stop_xdg_dbus_proxy(app_id, name)
            cleaned += 1
            print(f"Cleaned up proxy for {name}")

    # Clean up orphan socket directories (container fully removed)
    base_dir = os.path.dirname(_proxy_socket_dir("x"))
    known_names = set(name for _, name in running + stopped)
    if os.path.isdir(base_dir):
        for entry in os.listdir(base_dir):
            path = os.path.join(base_dir, entry)
            if not os.path.isdir(path):
                continue
            if entry not in known_names:
                shutil.rmtree(path, ignore_errors=True)
                cleaned += 1
                print(f"Cleaned up orphan proxy directory for {entry}")

    # Clean up orphan .desktop files (container fully removed)
    desktop_dir = os.path.expanduser("~/.local/share/applications")
    known_app_ids = set(a for a, _ in running + stopped)
    if os.path.isdir(desktop_dir):
        for entry in os.listdir(desktop_dir):
            if not entry.startswith("podsock_") or not entry.endswith(".desktop"):
                continue
            app_id = entry[:-8]
            if app_id not in known_app_ids:
                _delete_desktop_file(app_id)
                cleaned += 1
                print(f"Cleaned up orphan .desktop file for {app_id}")

    # Clean up stray systemd units for stopped/orphan containers
    try:
        units_out = subprocess.run(
            ["systemctl", "--user", "list-units", "--all", "--plain", "--no-legend", "app-podsock_*.service"],
            capture_output=True, text=True, check=False,
        )
        for line in units_out.stdout.strip().splitlines():
            parts = line.split()
            if not parts:
                continue
            unit = parts[0]
            if not unit.startswith("app-podsock_") or not unit.endswith(".service"):
                continue
            app_id = unit[len("app-"):-len(".service")]
            if app_id not in known_app_ids:
                subprocess.run(["systemctl", "--user", "stop", unit],
                              check=False, capture_output=True)
                cleaned += 1
                print(f"Stopped orphan systemd unit {unit}")
    except FileNotFoundError:
        pass

    print(f"Cleaned up {cleaned} item(s), preserved {len(running)} running container(s)")


def _stop_xdg_dbus_proxy(app_id, name, remove_dir=False):
    """Stop the proxy. Only delete .desktop file when remove_dir=True (i.e., on rm)."""
    unit_name = f"app-{app_id}.service"
    try:
        subprocess.run(["systemctl", "--user", "stop", unit_name],
                       check=False, capture_output=True)
    except FileNotFoundError:
        pass
    socket_dir = _proxy_socket_dir(name)
    # Also kill fallback proxy via PID file if present
    pid_path = os.path.join(socket_dir, "proxy.pid")
    if os.path.exists(pid_path):
        try:
            with open(pid_path, "r", encoding="utf-8") as f:
                pid = int(f.read().strip())
            os.kill(pid, 15)
        except (ValueError, ProcessLookupError, OSError):
            pass
    # Remove socket and pid file; keep directory so podman mount stays valid
    socket_path = _proxy_socket_path(name)
    for p in (socket_path, pid_path):
        if os.path.exists(p):
            os.unlink(p)
    if remove_dir and os.path.isdir(socket_dir):
        shutil.rmtree(socket_dir, ignore_errors=True)
        _delete_desktop_file(app_id)


def _podman_inspect_labels(name_or_id):
    """Return dict of labels for a container, or empty dict on error."""
    try:
        out = subprocess.run(
            ["podman", "inspect", "--format", "json", name_or_id],
            capture_output=True, text=True, check=False,
        )
        if out.returncode != 0:
            return {}
        data = json.loads(out.stdout)
        if isinstance(data, list) and data:
            return data[0].get("Config", {}).get("Labels") or {}
        return {}
    except Exception:
        return {}


def _extract_container_name(args):
    """Extract --name value from args; return None if not found."""
    for i, arg in enumerate(args):
        if arg.startswith("--name="):
            return arg[len("--name="):]
        if arg == "--name" and i + 1 < len(args):
            return args[i + 1]
    return None


def _fuse_mount_fstype(path):
    """Return the fstype if `path` is a mount point backed by FUSE, else None.

    A FUSE filesystem (such as the xdg-document-portal at $XDG_RUNTIME_DIR/doc)
    is owned by the user namespace that mounted it. The kernel denies access to
    FUSE mounts from a *different* user namespace, even when the new namespace
    is a descendant of the owning one.

    crun (Podman's default OCI runtime) pre-opens bind-mount sources with
    open_tree() in the host and then stats them via /proc/self/fd from inside
    the container's new user namespace. FUSE mounts fail that stat, producing:

        crun: cannot stat /proc/self/fd/NN: Permission denied: OCI permission denied

    This is not a crun-specific quirk. Any rootless container runtime that
    creates a new user namespace hits the same kernel restriction. Other
    podman-based projects (toolbox, distrobox) also cannot make the document
    store available inside their containers without an upstream fix from either
    xdg-document-portal (adding the allow_other mount option) or crun (falling
    back to a different bind-mount strategy for FUSE sources).

    Until either upstream fix lands, such a mount cannot be bind-mounted into a
    rootless container and must be skipped. (podman create only writes config.json,
    so the failure only appears later at start, when crun actually performs the
    mounts.)
    """
    real = os.path.realpath(path)
    try:
        with open("/proc/self/mountinfo", "r", encoding="utf-8") as f:
            mountinfo = f.read()
    except OSError:
        return None
    return _parse_fuse_fstype(mountinfo, real)


def _parse_fuse_fstype(mountinfo, target):
    """Parse /proc/self/mountinfo text; return fuse fstype if `target` is a FUSE mount."""
    for line in mountinfo.splitlines():
        # Format: ... <mount point> ... - <fstype> <source> <super opts>
        before_sep, sep, after_sep = line.partition(" - ")
        if not sep:
            continue
        left = before_sep.split()
        if len(left) < 5:
            continue
        # mount point is the 5th field; undo octal escapes for special chars.
        mount_point = left[4].replace("\\040", " ").replace("\\011", "\t")
        if mount_point != target:
            continue
        fields = after_sep.split()
        if fields and fields[0].startswith("fuse"):
            return fields[0]
    return None


def _portal_flag_args(name, dryrun=False):
    """Return extra podman args for +D (mounts + env)."""
    socket_dir = _proxy_socket_dir(name)
    doc_path = os.path.join(PODSOCK_RTDIR, "doc")
    # Mount the persistent directory (not the socket file) so that podman
    # can start the container even when the proxy is not yet running.
    proxy_mount = f"{PODSOCK_RTDIR}/podsock_proxy"
    args = [
        f"--env=DBUS_SESSION_BUS_ADDRESS=unix:path={proxy_mount}/bus.sock",
        f"--volume={socket_dir}:{proxy_mount}:ro",
    ]
    # The document portal (FileChooser) doc store is optional. Only bind-mount
    # it when it is a plain, accessible directory. A FUSE mount (the usual case
    # for xdg-document-portal on a real desktop) cannot be bind-mounted into a
    # rootless container because the kernel denies cross-user-namespace access
    # to FUSE filesystems. This affects all rootless tools (crun, toolbox,
    # distrobox) and cannot be fixed from podsock's side. Skipping the mount
    # lets the container start; portal D-Bus access still works through the proxy.
    fuse_fstype = _fuse_mount_fstype(doc_path)
    if fuse_fstype:
        print(f"WARNING: {doc_path} is a {fuse_fstype} mount and cannot be bind-mounted into",
              file=sys.stderr)
        print("         a rootless container; skipping it. The document portal store will be",
              file=sys.stderr)
        print("         unavailable, but other portals still work via the D-Bus proxy.",
              file=sys.stderr)
    elif os.path.isdir(doc_path) and os.access(doc_path, os.R_OK | os.X_OK):
        args.append(f"--volume={doc_path}:{doc_path}")
    else:
        print(f"WARNING: {doc_path} not accessible; FileChooser portal may not work",
              file=sys.stderr)
    return args


# ---------------------------------------------------------------------------
# Flag expansion
# ---------------------------------------------------------------------------

def _expand_flag(char):
    """Expand a single podsock flag char into podman args."""
    # Terminal flags
    if char == "t":
        return [
            "--interactive", "--tty",
            f"--env=TERM={os.environ.get('TERM', 'xterm')}",
        ]
    elif char == "T":
        return ["--interactive", "--tty", "--env=TERM=xterm-256color"]

    # Display
    elif char == "w":
        wl = os.environ.get("WAYLAND_DISPLAY")
        if not wl:
            die("Error: WAYLAND_DISPLAY not set")
        xdg = os.environ.get("XDG_RUNTIME_DIR")
        if not xdg:
            die("Error: XDG_RUNTIME_DIR not set")
        sock = os.path.join(xdg, wl)
        if not os.path.exists(sock) or not stat.S_ISSOCK(os.stat(sock).st_mode):
            die(f"Error: Wayland socket not found: {sock}")
        return [
            f"--env=WAYLAND_DISPLAY={wl}",
            f"--volume={sock}:{PODSOCK_RTDIR}/{wl}:ro",
        ]

    # Audio forwarding
    elif char == "p":
        xdg = os.environ.get("XDG_RUNTIME_DIR")
        if not xdg:
            die("Error: XDG_RUNTIME_DIR not set")
        playback_sock = os.path.join(xdg, "pipewire-0-playback")
        if not os.path.exists(playback_sock) or not stat.S_ISSOCK(os.stat(playback_sock).st_mode):
            installed = _ensure_pipewire_playback_configs()
            if installed:
                die(
                    "Error: PipeWire playback-only socket not found.\n"
                    "Host-side config files were installed. Restart PipeWire to activate:\n"
                    "  systemctl --user restart pipewire wireplumber\n"
                    "Then retry +p."
                )
            else:
                die(
                    "Error: PipeWire playback-only socket not found.\n"
                    "Host-side config files are already installed but the socket\n"
                    "is not available. Ensure PipeWire is running:\n"
                    "  systemctl --user restart pipewire wireplumber\n"
                    "Then retry +p."
                )
        return [
            f"--env=PIPEWIRE_REMOTE=pipewire-0-playback",
            f"--volume={playback_sock}:{PODSOCK_RTDIR}/pipewire-0-playback:ro",
        ]
    elif char == "P":
        xdg = os.environ.get("XDG_RUNTIME_DIR")
        if not xdg:
            die("Error: XDG_RUNTIME_DIR not set")
        pw_sock = os.path.join(xdg, "pipewire-0")
        pulse_sock = os.path.join(xdg, "pulse", "native")
        has_pw = os.path.exists(pw_sock) and stat.S_ISSOCK(os.stat(pw_sock).st_mode)
        has_pulse = os.path.exists(pulse_sock) and stat.S_ISSOCK(os.stat(pulse_sock).st_mode)
        if not has_pw and not has_pulse:
            die(
                f"Error: No audio socket found.\n"
                f"  Tried PipeWire: {pw_sock}\n"
                f"  Tried PulseAudio: {pulse_sock}"
            )
        args = []
        if has_pw:
            args.append(f"--volume={pw_sock}:{PODSOCK_RTDIR}/pipewire-0:ro")
        if has_pulse:
            args.append(f"--volume={pulse_sock}:{PODSOCK_RTDIR}/pulse/native:ro")
            args.append(f"--env=PULSE_SERVER=unix:{PODSOCK_RTDIR}/pulse/native")
        return args

    # SSH forwarding
    elif char == "s":
        ssh = os.environ.get("SSH_AUTH_SOCK")
        if not ssh:
            die("Error: SSH_AUTH_SOCK not set")
        if not os.path.exists(ssh) or not stat.S_ISSOCK(os.stat(ssh).st_mode):
            die(f"Error: SSH socket not found: {ssh}")
        return [
            f"--env=SSH_AUTH_SOCK={PODSOCK_RTDIR}/ssh-agent.socket",
            f"--volume={ssh}:{PODSOCK_RTDIR}/ssh-agent.socket:ro",
        ]

    # Hardware / capabilities
    elif char == "g":
        if not os.path.isdir("/dev/dri"):
            die("Error: /dev/dri not found")
        return ["--device", "/dev/dri"]

    elif char == "n":
        return [
            "--network=host",
            "--cap-add=NET_RAW,NET_ADMIN,NET_BIND_SERVICE",
        ]
    elif char == "d":
        return [
            "--cap-add=SYS_PTRACE,PERFMON",
            "--security-opt", "seccomp=unconfined",
        ]

    elif char == "f":
        if not os.path.exists("/dev/fuse"):
            die("Error: /dev/fuse not found. Load the fuse kernel module:\n"
                "  sudo modprobe fuse")
        return ["--device", "/dev/fuse", "--cap-add=SYS_ADMIN"]

    # App registration / portal access (handled in main(), not here)
    elif char in ("A", "D"):
        return []

    return []


def _find_first_positional(args, start=0, extra_bool_opts=None, short_value_opts=None):
    """Return index of first positional arg starting at start, or -1 if none."""
    bool_opts = _BOOL_LONG_OPTS | extra_bool_opts if extra_bool_opts else _BOOL_LONG_OPTS
    short_vals = short_value_opts or set()
    skip_next = False
    for i in range(start, len(args)):
        if skip_next:
            skip_next = False
            continue
        arg = args[i]
        if arg == "--":
            if i + 1 < len(args):
                return i + 1
            return -1
        if arg.startswith("+"):
            continue
        if arg.startswith("-"):
            if arg.startswith("--"):
                if "=" not in arg and arg not in bool_opts:
                    skip_next = True
            elif len(arg) == 2 and arg[1] in short_vals:
                skip_next = True
            continue
        return i
    return -1


def _find_subcommand(args):
    """Return (subcommand, subcommand_idx) before --, skipping +flags and -options."""
    skip_next = False
    for i, arg in enumerate(args):
        if arg == "--":
            break
        if skip_next:
            skip_next = False
            continue
        if arg.startswith("+"):
            continue
        if arg.startswith("-"):
            # Long option without '=': next arg is likely its value
            if arg.startswith("--") and "=" not in arg and arg not in _BOOL_LONG_OPTS:
                skip_next = True
            # Short option that takes a value: next arg is its value
            elif len(arg) == 2 and arg[1] in _GLOBAL_SHORT_VAL_OPTS:
                skip_next = True
            continue
        return arg, i
    return None, -1


def main():
    """Entry point: parse arguments, expand +flags, and exec podman."""
    args = sys.argv[1:]

    if not args:
        print("Podsock - podman wrapper with +flags")
        print()
        print("Usage: podsock [+flags] <command> [args...]")
        print()
        print("Run 'podsock --help' for full help, or 'man podsock' for the manual.")
        sys.exit(0)

    if len(args) == 1 and args[0] == "--bash-completion":
        print_bash_completion()
        sys.exit(0)

    # ---- Pass 1: parse arguments ----
    subcommand, subcommand_idx = _find_subcommand(args)

    flags = []
    double_dash_idx = -1
    for i, arg in enumerate(args):
        if arg == "--":
            double_dash_idx = i
            break
        if arg.startswith("+"):
            flags.append(arg)

    # ---- Help handling ----
    # Scan args before -- and before the first positional after the subcommand.
    # Skip the subcommand itself and values of long/short options.
    help_found = False
    version_found = False
    skip_next = False
    for i, arg in enumerate(args):
        if arg == "--":
            break
        if skip_next:
            skip_next = False
            continue
        if arg.startswith("+"):
            continue
        if arg.startswith("-"):
            if arg.startswith("--"):
                if "=" not in arg and arg not in _BOOL_LONG_OPTS:
                    skip_next = True
            elif len(arg) == 2 and arg[1] not in "itldas":
                skip_next = True
            if arg in ("-h", "--help"):
                help_found = True
                break
            if arg == "--version":
                version_found = True
                break
            continue
        if subcommand is not None and i == subcommand_idx:
            continue
        break
    if version_found:
        podman_bin = shutil.which("podman")
        if podman_bin:
            subprocess.run([podman_bin, "--version"], check=False)
        else:
            print("Error: podman not found in PATH", file=sys.stderr)
        print(f"podsock {__version__}")
        sys.exit(0)
    if help_found:
        show_help(subcommand)
        sys.exit(0)

    if subcommand == "help":
        target = None
        for i, arg in enumerate(args):
            if arg == "help" and i + 1 < len(args):
                target = args[i + 1]
                break
        show_help(target)
        sys.exit(0)

    # ---- Validate +flags ----
    allowed = set(_ALLOWED_FLAGS.get(subcommand, "?"))

    dryrun = False
    seen = set()
    for group in flags:
        for char in group[1:]:
            if char not in allowed:
                die(f"Error: +{char} flag is not supported for this command")
            if char == "?":
                dryrun = True
            seen.add(char)
    if "t" in seen and "T" in seen:
        die("Error: +t and +T are mutually exclusive")

    has_A = "A" in seen
    has_D = "D" in seen
    portal = has_D
    app_reg = has_A or has_D

    # ---- Pass 2: build command ----
    cmd = ["podman"]
    flag_args = []
    for group in flags:
        for char in group[1:]:
            if char != "?":
                flag_args.extend(_expand_flag(char))

    # Everything except +flags (before --)
    remaining = [
        arg for i, arg in enumerate(args)
        if (double_dash_idx >= 0 and i >= double_dash_idx) or not arg.startswith("+")
    ]

    # ---- Subcommand dispatch ----
    if subcommand == "shell":
        # Prepend global podman options (shell rewrites the subcommand)
        cmd.extend(a for a in args[:subcommand_idx] if not a.startswith("+"))
        shell_idx = remaining.index("shell")
        rem_after_shell = remaining[shell_idx + 1:]
        container_idx = _find_first_positional(
            args, subcommand_idx + 1,
            frozenset([
                "--interactive", "--tty", "--privileged", "--latest",
                "--detach", "--env-host", "--init"
            ]),
            frozenset("euwp"),
        )
        if container_idx == -1:
            die(f"Usage: {sys.argv[0]} shell <container> [command]")
        cmd.append("exec")
        cmd.extend(flag_args)
        cmd.append("-it")
        cmd.extend(rem_after_shell)
        has_tail = any(not a.startswith("+") for a in args[container_idx + 1:])
        if not has_tail:
            cmd.append("bash")
    elif subcommand == "helm":
        # Prepend global podman options (helm rewrites the subcommand)
        cmd.extend(a for a in args[:subcommand_idx] if not a.startswith("+"))
        helm_idx = remaining.index("helm")
        rem_after_helm = remaining[helm_idx + 1:]
        container_idx = _find_first_positional(
            args, subcommand_idx + 1,
            frozenset(["--attach", "--interactive", "--latest", "--all", "--sig-proxy"]),
        )
        if container_idx == -1:
            die(f"Usage: {sys.argv[0]} helm <container>")
        container_arg = args[container_idx]
        # If container was created with +A/+D, ensure .desktop and proxy are ready
        labels = _podman_inspect_labels(container_arg)
        app_id = labels.get("podsock.app_id")
        container_name = labels.get("podsock.name") or container_arg
        if app_id:
            _create_desktop_file(app_id, container_name, dryrun=dryrun)
            if labels.get("podsock.portal") == "true":
                _start_xdg_dbus_proxy(app_id, container_name, dryrun=dryrun)
        cmd.append("start")
        cmd.extend(flag_args)
        cmd.append("-ai")
        cmd.extend(rem_after_helm)
    elif subcommand in ("run", "create"):
        cmd.append(subcommand)
        cmd.extend(flag_args)
        cmd.extend([
            "--tmpfs", f"{PODSOCK_RTDIR}:mode=0700,U",
            "--security-opt", "label=disable",
            "--userns", "keep-id",
            f"--env=XDG_RUNTIME_DIR={PODSOCK_RTDIR}",
        ])
        if PODSOCK_INIT == "1":
            cmd.append("--init")

        if app_reg:
            container_name = _extract_container_name(remaining)
            if not container_name:
                # Generate a deterministic name so the .desktop file and socket path are stable
                container_name = os.urandom(4).hex()
                if not dryrun:
                    print(f"WARNING: +A/+D used without --name; auto-generated name '{container_name}'",
                          file=sys.stderr)
                cmd.append(f"--name={container_name}")
            app_id = _generate_app_id(container_name)
            cmd.append(f"--label=podsock.app_id={app_id}")
            cmd.append(f"--label=podsock.name={container_name}")
            if portal:
                cmd.append("--label=podsock.portal=true")
            if not dryrun:
                _create_desktop_file(app_id, container_name, dryrun=dryrun)
            if portal:
                # Start proxy even for 'create' because podman validates bind-mount sources.
                socket_path = _start_xdg_dbus_proxy(app_id, container_name, dryrun=dryrun)
                if not dryrun and not os.path.exists(socket_path):
                    die("Error: proxy socket did not appear")
                cmd.extend(_portal_flag_args(container_name, dryrun=dryrun))

        for arg in remaining:
            if arg == subcommand:
                continue
            cmd.append(arg)
    elif subcommand == "rm":
        # Pre-cleanup for containers that had +A/+D
        container_idx = _find_first_positional(
            args, subcommand_idx + 1,
            frozenset(["--force", "--all", "--latest", "--volumes", "--depend"]),
        )
        if container_idx != -1:
            container_arg = args[container_idx]
            labels = _podman_inspect_labels(container_arg)
            app_id = labels.get("podsock.app_id")
            container_name = labels.get("podsock.name") or container_arg
            if app_id:
                _stop_xdg_dbus_proxy(app_id, container_name, remove_dir=True)
        cmd.append("rm")
        for arg in remaining:
            if arg == subcommand:
                continue
            cmd.append(arg)
    elif subcommand == "start":
        # Similar to helm: ensure proxy is running for portal containers
        container_idx = _find_first_positional(
            args, subcommand_idx + 1,
            frozenset(["--attach", "--interactive", "--latest", "--all", "--sig-proxy"]),
        )
        if container_idx != -1:
            container_arg = args[container_idx]
            labels = _podman_inspect_labels(container_arg)
            app_id = labels.get("podsock.app_id")
            container_name = labels.get("podsock.name") or container_arg
            if app_id:
                _create_desktop_file(app_id, container_name, dryrun=dryrun)
                if labels.get("podsock.portal") == "true":
                    _start_xdg_dbus_proxy(app_id, container_name, dryrun=dryrun)
        cmd.append("start")
        for arg in remaining:
            if arg == subcommand:
                continue
            cmd.append(arg)
    elif subcommand == "cleanup":
        _cleanup_dbus()
        sys.exit(0)
    elif subcommand:
        cmd.append(subcommand)
        cmd.extend(flag_args)
        for arg in remaining:
            if arg == subcommand:
                continue
            cmd.append(arg)
    else:
        cmd.extend(flag_args)
        cmd.extend(remaining)

    # ---- Execute or dry-run ----
    if dryrun or os.environ.get("PODSOCK_DRYRUN") == "1":
        print(" ".join(shlex.quote(a) for a in cmd))
    else:
        os.execvp("podman", cmd)


if __name__ == "__main__":
    main()
