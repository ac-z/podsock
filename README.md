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
| `+p` | PipeWire playback-only audio forwarding | `run`, `create` |
| `+P` | PipeWire full audio forwarding (playback + capture) | `run`, `create` |
| `+n` | Host network with extra capabilities | `run`, `create` |
| `+d` | Debug capabilities (`ptrace`, `perfmon`) | `run`, `create` |
| `+A` | Register as a desktop app (creates `.desktop` launcher) | `run`, `create` |
| `+D` | Enable XDG Desktop Portal access (filtered D-Bus, implies `+A`) | `run`, `create` |
| `+f` | FUSE filesystem support (e.g. sshfs) | `run`, `create` |
| `+?` | Dry run (print the podman command without executing) | all |

Flags can be chained: `+Tdn` gives you terminal, debug, and network.
`+t`/`+T` and `+p`/`+P` are mutually exclusive pairs.

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

> [!WARNING]
> `+f` grants `CAP_SYS_ADMIN`, one of the most powerful Linux capabilities. In addition to FUSE mounts, `SYS_ADMIN` enables a broad range of privileged operations (mount/umount, namespace manipulation, various sysadmin actions). Only use `+f` with trusted container images.

> [!NOTE]
> **`+f` prerequisites:** The `fuse` kernel module must be loaded on the host (`/dev/fuse` must exist). On modern systemd distros (Fedora, Ubuntu, Debian, Arch), `/dev/fuse` is world-readable/writable by default via udev rules — no group membership needed. The container image must have `fusermount`/`fusermount3` and the desired FUSE filesystem tool (e.g., `sshfs`) installed. If `/dev/fuse` is not world-accessible on your system, you may need `--group-add keep-groups` (crun only).

## Audio Forwarding

PipeWire audio forwarding requires a PipeWire host.

- **`+P`** forwards the host audio sockets. It tries PipeWire first, then PulseAudio — whichever is present (or both). The container gets the same audio access as any host application: playback and capture both work. Works on PipeWire-only, PulseAudio-only, and mixed systems.

- **`+p`** forwards a **playback-only** PipeWire socket. Containers cannot access capture (microphone) devices. On first use, podsock auto-installs the required host-side configs under `~/.config/` and prompts you to restart PipeWire:

  ```bash
  podsock run +p --rm -it myimage
  # First run: configs are written, then:
  # Error: PipeWire playback-only socket not found.
  # Host-side config files were installed. Restart PipeWire to activate:
  #   systemctl --user restart pipewire wireplumber
  # Then retry +p.
  ```

  After restarting PipeWire, `pipewire-0-playback` will exist in `$XDG_RUNTIME_DIR` and `+p` will work transparently.

  > [!NOTE]
  > `+p` only restricts PipeWire-native clients. PulseAudio clients inside the container will not have audio (the PulseAudio socket is not forwarded), which is a safe default. If you need PulseAudio compatibility, use `+P` instead.

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

podsock run +P --rm -it myimage
# Forwards the host PipeWire socket (and PulseAudio socket if present)
# so the container can play and record audio.

podsock run +p --rm -it myimage
# Forwards a playback-only PipeWire socket.
# Audio playback works; recording is blocked by host-side WirePlumber rules.

podsock run +D --rm -it myimage
# Runs with a filtered D-Bus proxy for XDG Desktop Portal access
# (file chooser, notifications, screen sharing, etc.)

podsock run +Tfs --rm -it myimage
# Terminal + FUSE support + SSH agent forwarding
# Inside the container:
#   sshfs user@host:/path /mnt/remote

podsock +? run ubuntu echo hello
# Prints: podman run --tmpfs /run/user/1000:mode=0700,U --security-opt label=disable
#         --userns keep-id --env=XDG_RUNTIME_DIR=/run/user/1000 --init ubuntu echo hello
```

## Installation

### Dependencies

Required:
* Python 3 (tested with 3.12+)
* Podman

Optional (for `+p`/`+P` audio forwarding):
* PipeWire (host) — required for audio socket forwarding

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

### Manual

The man page is installed to `$(PREFIX)/share/man/man1/podsock.1`. View it with `man podsock`.

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
