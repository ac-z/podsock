#!/usr/bin/env python3
"""Podsock - podman wrapper with +flags."""

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

    # Detect subcommand to determine valid +flags
    for ((i=1; i<COMP_CWORD; i++)); do
        case "${COMP_WORDS[i]}" in
            run|create) subcmd="${COMP_WORDS[i]}"; break ;;
            shell|helm) subcmd="${COMP_WORDS[i]}"; break ;;
        esac
    done

    # Complete +flags
    if [[ "$cur" == +* ]]; then
        local flags=""
        case "$subcmd" in
            run|create) flags="+t +T +w +s +g +n +d +?" ;;
            shell|helm) flags="+?" ;;
            *) flags="+?" ;;
        esac
        COMPREPLY=($(compgen -W "$flags" -- "$cur"))
        return 0
    fi

    # Delegate to podman completion after stripping +flags and mapping subcommands
    local podman_words=("podman")
    local podman_cword=0
    local found=0

    for ((i=1; i<=${#COMP_WORDS[@]}-1; i++)); do
        local w="${COMP_WORDS[i]}"
        [[ "$w" == +* ]] && continue
        podman_words+=("$w")
        if [[ $i -lt $COMP_CWORD ]]; then
            ((podman_cword++))
        elif [[ $i -eq $COMP_CWORD ]]; then
            podman_cword=$((${#podman_words[@]} - 1))
        fi
        if [[ $found -eq 0 ]]; then
            case "$w" in
                shell) podman_words[-1]="exec"; found=1 ;;
                helm)  podman_words[-1]="start"; found=1 ;;
                run|create|exec|ps|logs|images|build|push|pull|import|export|stats|top|pause|unpause|stop|start|restart|kill|rm|wait|mount|umount|attach|diff|inspect|history|info|version|generate|play|kube|manifest|network|volume|pod|system) found=1 ;;
            esac
        fi
    done

    if type -t _podman &>/dev/null; then
        local old_words=("${COMP_WORDS[@]}")
        local old_cword=$COMP_CWORD
        local old_line=$COMP_LINE
        local old_point=$COMP_POINT
        COMP_WORDS=("${podman_words[@]}")
        COMP_CWORD=$podman_cword
        COMP_LINE="${COMP_WORDS[*]}"
        COMP_POINT=${#COMP_LINE}
        _podman
        COMP_WORDS=("${old_words[@]}")
        COMP_CWORD=$old_cword
        COMP_LINE=$old_line
        COMP_POINT=$old_point
    fi
}

complete -F _podsock podsock
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


def _find_first_positional(args, start=0, extra_bool_opts=None):
    """Return index of first positional arg starting at start, or -1 if none."""
    bool_opts = _BOOL_LONG_OPTS | extra_bool_opts if extra_bool_opts else _BOOL_LONG_OPTS
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
            if arg.startswith("--") and "=" not in arg and arg not in bool_opts:
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
    if any(a in ("-h", "--help") for a in args):
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
    for group in flags:
        for char in group[1:]:
            if char not in allowed:
                die(f"Error: +{char} flag is not supported for this command")
            if char == "?":
                dryrun = True

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
            frozenset(["--interactive", "--tty", "--privileged", "--latest", "--detach", "--env-host", "--init"]),
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
