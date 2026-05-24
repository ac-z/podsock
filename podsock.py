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


def main():
    """Entry point: parse arguments, expand +flags, and exec podman."""
    args = sys.argv[1:]

    if not args:
        os.execvp("podman", ["podman"])

    # Find subcommand and collect +flags that appear BEFORE it
    subcommand = None
    subcommand_idx = -1
    flags = []
    for i, arg in enumerate(args):
        if arg == "--":
            break
        if subcommand is None:
            if arg.startswith("+"):
                flags.append(arg)
            elif arg not in ("-h", "--help"):
                subcommand = arg
                subcommand_idx = i

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
    elif subcommand in ("shell", "helm"):
        allowed = set("?")
    else:
        allowed = set("?")

    # Validate only +flags that appear before the subcommand
    for group in flags:
        for char in group[1:]:
            if char not in allowed:
                die(f"Error: +{char} flag is not supported for this command")

    # Build the command. Only expand +args before the subcommand;
    # everything after the subcommand passes through literally.
    cmd = ["podman"]
    dryrun = False
    i = 0
    while i < len(args):
        arg = args[i]

        if arg.startswith("+") and (subcommand_idx < 0 or i < subcommand_idx):
            for char in arg[1:]:
                if char == "?":
                    dryrun = True
                elif char == "t":
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

        elif arg == "--":
            cmd.append("--")
            i += 1
            while i < len(args):
                cmd.append(args[i])
                i += 1
            break

        elif arg in ("run", "create"):
            cmd.append(arg)
            cmd.extend([
                "--tmpfs", f"{PODSOCK_RTDIR}:mode=0700,U",
                "--security-opt", "label=disable",
                "--userns", "keep-id",
                f"--env=XDG_RUNTIME_DIR={PODSOCK_RTDIR}",
            ])
            if PODSOCK_INIT == "1":
                cmd.append("--init")

        elif arg == "shell":
            if i + 1 >= len(args):
                die(f"Usage: {sys.argv[0]} shell <container> [command]")
            cmd.extend(["exec", "-it", args[i + 1]])
            if i + 2 < len(args):
                cmd.extend(args[i + 2:])
            else:
                cmd.append("bash")
            i = len(args)

        elif arg == "helm":
            if i + 1 >= len(args):
                die(f"Usage: {sys.argv[0]} helm <container>")
            cmd.extend(["start", "-ai", args[i + 1]])
            i = len(args)

        else:
            cmd.append(arg)

        i += 1

    if dryrun or os.environ.get("PODSOCK_DRYRUN") == "1":
        print(" ".join(shlex.quote(a) for a in cmd))
    else:
        os.execvp("podman", cmd)


if __name__ == "__main__":
    main()
