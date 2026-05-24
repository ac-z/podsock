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

import os
import shlex
import stat
import subprocess
import sys


PODSOCK_INIT = os.environ.get("PODSOCK_INIT", "1")
PODSOCK_RTDIR = os.environ.get("PODSOCK_RTDIR", f"/run/user/{os.getuid()}")

_BOOL_LONG_OPTS = frozenset(["--help", "--version", "--syslog"])
_FLAG_DESCS = {
    "t": "Terminal interactivity (uses $TERM)",
    "T": "Terminal interactivity (forces xterm-256color)",
    "w": "Wayland display forwarding",
    "s": "SSH agent socket forwarding",
    "g": "GPU/graphics device access",
    "n": "Host network with extra capabilities",
    "d": "Debug capabilities (ptrace, perfmon)",
    "?": "Dry run (print command without executing)",
}
_ALLOWED_FLAGS = {"run": "tTwsgnd?", "create": "tTwsgnd?"}


def die(msg):
    """Print message to stderr and exit with code 1."""
    print(msg, file=sys.stderr)
    sys.exit(1)


def show_help(subcommand=None):
    """Display podsock and podman help for the given subcommand."""
    print("Podsock - podman wrapper with +flags")
    print()
    print("Usage: podsock [+flags] <command> [args...]")
    print()

    if subcommand in _ALLOWED_FLAGS:
        flags = list(_ALLOWED_FLAGS[subcommand])
    elif subcommand in ("shell", "helm"):
        flags = ["?"]
    elif subcommand == "help":
        print("Show help for a podsock command.")
        print("Usage: podsock help <command>")
        return
    else:
        flags = ["?"] if subcommand else []

    if subcommand:
        print(f"Available +flags for '{subcommand}':")
        for f in flags:
            print(f"  +{f}  {_FLAG_DESCS[f]}")
        print()

    podman_cmd = {"shell": "exec", "helm": "start"}.get(subcommand, subcommand)

    if subcommand:
        print(f"--- Podman help for '{podman_cmd}' ---")
        subprocess.run(["podman", podman_cmd, "--help"], check=False)
    else:
        print("Subcommands:")
        print("  shell <container> [command]  Run a shell (or command) in a running container")
        print("  helm <container>             Start a container interactively")
        print()
        print("Use 'podsock <command> --help' for command-specific help.")
        print()
        print("--- Podman help ---")
        subprocess.run(["podman", "--help"], check=False)


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
            run|create) avail="tTwsgnd?" ;;
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

    # Inject podsock-specific subcommands when at the subcommand position
    if [[ -z "$subcmd" && "$cur" != -* ]]; then
        while IFS= read -r line; do
            COMPREPLY+=("$line")
        done < <(compgen -W "shell helm" -- "$cur")
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

complete -o default -F _podsock podsock
""")


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
            die(f"Error: Wayland socket not found at {sock}")
        return [
            f"--env=WAYLAND_DISPLAY={wl}",
            f"--volume={sock}:{PODSOCK_RTDIR}/{wl}:ro",
        ]

    # SSH forwarding
    elif char == "s":
        ssh = os.environ.get("SSH_AUTH_SOCK")
        if not ssh:
            die("Error: SSH_AUTH_SOCK not set")
        if not os.path.exists(ssh) or not stat.S_ISSOCK(os.stat(ssh).st_mode):
            die(f"Error: SSH socket not found at {ssh}")
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
            continue
        return arg, i
    return None, -1


def main():
    """Entry point: parse arguments, expand +flags, and exec podman."""
    args = sys.argv[1:]

    if not args:
        os.execvp("podman", ["podman"])

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
            continue
        if subcommand is not None and i == subcommand_idx:
            continue
        break
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
            frozenset("euw"),
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
        for arg in remaining:
            if arg == subcommand:
                continue
            cmd.append(arg)
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
