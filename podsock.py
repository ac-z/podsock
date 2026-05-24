#!/usr/bin/env python3
"""Podsock - podman wrapper with +flags."""

import os
import shlex
import stat
import subprocess
import sys


PODSOCK_INIT = os.environ.get("PODSOCK_INIT", "1")
PODSOCK_RTDIR = os.environ.get("PODSOCK_RTDIR", f"/run/user/{os.getuid()}")


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

    if subcommand in ("run", "create"):
        flags = ["t", "T", "w", "s", "g", "n", "d", "?"]
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
        descs = {
            "t": "Terminal interactivity (uses $TERM)",
            "T": "Terminal interactivity (forces xterm-256color)",
            "w": "Wayland display forwarding",
            "s": "SSH agent socket forwarding",
            "g": "GPU/graphics device access",
            "n": "Host network with extra capabilities",
            "d": "Debug capabilities (ptrace, perfmon)",
            "?": "Dry run (print command without executing)",
        }
        for f in flags:
            print(f"  +{f}  {descs[f]}")
        print()

    podman_cmd = subcommand
    if subcommand == "shell":
        podman_cmd = "exec"
    elif subcommand == "helm":
        podman_cmd = "start"

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


def _expand_flag(char, cmd):
    """Expand a single podsock flag char into podman args."""
    if char == "t":
        cmd.extend([
            "--interactive", "--tty",
            f"--env=TERM={os.environ.get('TERM', 'xterm')}",
        ])
    elif char == "T":
        cmd.extend([
            "--interactive", "--tty",
            "--env=TERM=xterm-256color",
        ])
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
        cmd.append(f"--env=WAYLAND_DISPLAY={wl}")
        cmd.append(f"--volume={sock}:{PODSOCK_RTDIR}/{wl}:ro")
    elif char == "s":
        ssh = os.environ.get("SSH_AUTH_SOCK")
        if not ssh:
            die("Error: SSH_AUTH_SOCK not set")
        if not os.path.exists(ssh) or not stat.S_ISSOCK(os.stat(ssh).st_mode):
            die(f"Error: SSH socket not found at {ssh}")
        cmd.append(f"--env=SSH_AUTH_SOCK={PODSOCK_RTDIR}/ssh-agent.socket")
        cmd.append(f"--volume={ssh}:{PODSOCK_RTDIR}/ssh-agent.socket:ro")
    elif char == "g":
        if not os.path.isdir("/dev/dri"):
            die("Error: /dev/dri not found")
        cmd.extend(["--device", "/dev/dri"])
    elif char == "n":
        cmd.extend([
            "--network=host",
            "--cap-add=NET_RAW,NET_ADMIN,NET_BIND_SERVICE",
        ])
    elif char == "d":
        cmd.extend([
            "--cap-add=SYS_PTRACE,PERFMON",
            "--security-opt", "seccomp=unconfined",
        ])


def _find_subcommand(args):
    """Return (subcommand, subcommand_idx) before --, skipping +flags and -options."""
    # Long-form boolean options that do NOT consume a following value.
    _BOOL_LONG_OPTS = frozenset(["--help", "--version", "--syslog"])

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

    # ---- Pass 1: find subcommand, collect all +flags, find -- ----
    subcommand, subcommand_idx = _find_subcommand(args)
    flags = []
    double_dash_idx = -1
    for i, arg in enumerate(args):
        if arg == "--":
            double_dash_idx = i
            break
        if arg.startswith("+"):
            flags.append(arg)

    # Help detection
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

    # Determine allowed flags per subcommand
    if subcommand in ("run", "create"):
        allowed = set("tTwsgnd?")
    else:
        # shell, helm, and every other podman subcommand only support +?
        allowed = set("?")

    # Validate ALL +flags (wherever they appeared)
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
                _expand_flag(char, flag_args)

    # Everything except +flags (before --)
    remaining = []
    for i, arg in enumerate(args):
        if double_dash_idx >= 0 and i >= double_dash_idx:
            remaining.append(arg)
        elif not arg.startswith("+"):
            remaining.append(arg)

    if subcommand == "shell":
        # Prepend global podman options (shell rewrites the subcommand)
        for i in range(subcommand_idx):
            if not args[i].startswith("+"):
                cmd.append(args[i])
        if subcommand_idx + 1 >= len(args):
            die(f"Usage: {sys.argv[0]} shell <container> [command]")
        cmd.append("exec")
        cmd.extend(flag_args)
        cmd.extend(["-it", args[subcommand_idx + 1]])
        tail = [a for a in args[subcommand_idx + 2:] if not a.startswith("+")]
        if double_dash_idx >= 0:
            before_dd = [a for a in args[subcommand_idx + 2:double_dash_idx] if not a.startswith("+")]
            after_dd = args[double_dash_idx:]
            tail = before_dd + after_dd
        if tail:
            cmd.extend(tail)
        else:
            cmd.append("bash")
    elif subcommand == "helm":
        # Prepend global podman options (helm rewrites the subcommand)
        for i in range(subcommand_idx):
            if not args[i].startswith("+"):
                cmd.append(args[i])
        if subcommand_idx + 1 >= len(args):
            die(f"Usage: {sys.argv[0]} helm <container>")
        cmd.append("start")
        cmd.extend(flag_args)
        cmd.extend(["-ai", args[subcommand_idx + 1]])
        tail = [a for a in args[subcommand_idx + 2:] if not a.startswith("+")]
        if double_dash_idx >= 0:
            before_dd = [a for a in args[subcommand_idx + 2:double_dash_idx] if not a.startswith("+")]
            after_dd = args[double_dash_idx:]
            tail = before_dd + after_dd
        cmd.extend(tail)
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

    if dryrun or os.environ.get("PODSOCK_DRYRUN") == "1":
        print(" ".join(shlex.quote(a) for a in cmd))
    else:
        os.execvp("podman", cmd)


if __name__ == "__main__":
    main()
