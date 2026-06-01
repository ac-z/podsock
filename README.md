# Podsock 🧦

An opinionated podman CLI wrapper that adds convenient shorthand flags (`+t`, `+w`, `+D`, etc.) and helper subcommands (`shell`, `helm`) without hiding the underlying podman CLI. Most of what podsock does pertains to breaking isolation only as much as is needed for a given task.

## Quick Start

```bash
podsock run +Twg --rm -it ubuntu bash
podsock shell mycontainer
podsock helm mycontainer
```

## Available +flags

| Flag | Description | Applies to |
|------|-------------|------------|
| `+t` | Terminal interactivity (uses `$TERM`) | `run`, `create` |
| `+T` | Terminal interactivity (forces `xterm-256color`) | `run`, `create` |
| `+w` | Wayland display forwarding | `run`, `create` |
| `+s` | SSH agent socket forwarding | `run`, `create` |
| `+g` | GPU/graphics device access (`/dev/dri`) | `run`, `create` |
| `+n` | Host network with extra capabilities | `run`, `create` |
| `+d` | Debug capabilities (`ptrace`, `perfmon`) | `run`, `create` |
| `+A` | Register as a desktop app (creates `.desktop` launcher) | `run`, `create` |
| `+D` | Enable XDG Desktop Portal access (filtered D-Bus, implies `+A`) | `run`, `create` |
| `+?` | Dry run (print the podman command without executing) | all |

Flags can be chained: `+Tdn` gives you terminal, debug, and network.

## Subcommands

In addition to all standard podman subcommands, podsock provides:

- **shell** — run an interactive shell (or command) in a running container via `podman exec`:
  ```bash
  podsock shell mycontainer        # opens bash by default
  podsock shell mycontainer python # opens python
  ```

- **helm** — start an existing container interactively via `podman start`:
  ```bash
  podsock helm mycontainer
  ```

Standard podman options (e.g. `--user`, `--attach`) are passed through, but `+flags` other than `+?` are not supported for `shell` and `helm`.

- **cleanup** — stop stale D-Bus proxies and remove `.desktop` files for deleted containers:
  ```bash
  podsock cleanup
  ```
  This scans all containers with podsock labels. Running containers are left untouched. Stopped containers have their proxy stopped (to save resources). Fully removed containers have both their proxy directories and `.desktop` files cleaned up.

## Important Notes

> [!WARNING]
> Podsock always disables SELinux labeling and shares the host user's UID and username with the container.

> [!WARNING]
> `+D` does **not** filter individual portal interfaces. Access control is delegated to the desktop environment's permission dialogs. Treat untrusted apps with `+D` with the same caution as a Flatpak with full portal access.

> [!NOTE]
> The WORKDIR specified in the container image becomes the home directory for the host user inside the container. Ensure your image has a WORKDIR that is writable to all users, or adjust permissions via a root shell after creation.

> [!NOTE]
> Containers created with `+D` rely on podsock (or equivalent manual setup) to manage the D-Bus proxy lifecycle. After a host reboot, `podman start` will succeed (the mount source is a persistent directory), but D-Bus portal access inside the container will not work until the proxy is restarted. Use `podsock start` or `podsock helm` to automatically restart the proxy.

> [!NOTE]
> Containers created with `+A` have a `.desktop` launcher that references `podsock helm`, but `podman start` works fine without podsock.

## Examples

```bash
podsock run +Twg --rm -it ubuntu bash
# Runs: podman run --interactive --tty --env=TERM=xterm-256color
#       --env=WAYLAND_DISPLAY=wayland-0 --volume=/run/user/1000/wayland-0:/run/user/1000/wayland-0:ro
#       --device /dev/dri --tmpfs /run/user/1000:mode=0700,U --security-opt label=disable
#       --userns keep-id --env=XDG_RUNTIME_DIR=/run/user/1000 --init --rm -it ubuntu bash

podsock run +s --rm -it myimage
# Runs: podman run --env=SSH_AUTH_SOCK=/run/user/1000/ssh-agent.socket
#       --volume=/run/user/1000/ssh-agent.socket:/run/user/1000/ssh-agent.socket:ro
#       --tmpfs /run/user/1000:mode=0700,U --security-opt label=disable --userns keep-id
#       --env=XDG_RUNTIME_DIR=/run/user/1000 --init --rm -it myimage

podsock run +D --rm -it myimage
# Runs with a filtered D-Bus proxy for XDG Desktop Portal access
# (file chooser, notifications, screen sharing, etc.)

podsock +? run ubuntu echo hello
# Prints: podman run --tmpfs /run/user/1000:mode=0700,U --security-opt label=disable
#         --userns keep-id --env=XDG_RUNTIME_DIR=/run/user/1000 --init ubuntu echo hello
```

## Installation

### Dependencies

Required:
* Python 3 (tested with 3.14)
* Podman

Optional (for `+D` portal access):
* `xdg-dbus-proxy` — required for `+D`
* `systemd` (user session) — strongly recommended for per-container app IDs and proper portal permission tracking

Testing:
* Pytest

### Install

```bash
make install                    # ~/.local
sudo make install PREFIX=/usr/local
make install PREFIX=/usr DESTDIR=/tmp/stage  # packaging
```

### Uninstall

```bash
make uninstall
sudo make uninstall PREFIX=/usr/local
```

## Bash Completions

The install target sets up bash completion for `+flags`, subcommand mapping, and podman delegation.

For a bash alias:

```bash
# ~/.bashrc
alias pod='podsock'
```

Then run:
```bash
make completions ALIAS=pod
```

Or generate the script directly:
```bash
python3 podsock.py --bash-completion
```

## Directories

Podsock stores persistent state in `~/.var/podsock/` (proxy sockets). `.desktop` files created by `+A`/`+D` live in the standard `~/.local/share/applications/` directory.

## License

Licensed under the GNU General Public License v3.0. See [LICENSE](LICENSE).
