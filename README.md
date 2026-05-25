# Podsock 🧦

Podsock is an opinionated podman CLI wrapper that doesn't abstract away the underlying podman CLI. It adds convenient shorthand flags and subcommands for common container use cases. Most of what podsock does pertains to breaking isolation only as much as is needed for a given task. 

More and more commonly it is the case that we need things like nightly compilers and giant unsupervisable package manager ecosystems that carry with them inherent security risks.
Common tools like toolbox and distrobox are great for quickly installing and using OS-level packages from trusted distros to work in your home directory, but any namespace that can see your home directory is no place to run in-development software with sprawling dependencies.
Podsock is designed to facilitate fast setup of secure containers for desktop use, and fast access to running containers, while letting you trim down the podman flags more precisely later.

No containers created via podsock have any dependency on podsock. You won't get any surprises accessing your containers without it later.

> [!WARNING]
> In its current form, podsock always disables SELinux labeling and shares the host user's UID and username with the container.

> [!NOTE]
> The WORKDIR specified in the container image will be the home directory for the host user in the container. It is recommended to ensure your container image has a WORKDIR which is writable to all users, or to make changes via a root shell after container creation to ensure your user can write to $HOME.

## Usage

```bash
podsock [+flags] <podman-command> [args...]
```

### Available +flags

| Flag | Description | Applies to |
|------|-------------|------------|
| `+t` | Terminal interactivity (uses `$TERM`) | `run`, `create` |
| `+T` | Terminal interactivity (forces `xterm-256color`) | `run`, `create` |
| `+w` | Wayland display forwarding | `run`, `create` |
| `+s` | SSH agent socket forwarding | `run`, `create` |
| `+g` | GPU/graphics device access (`/dev/dri`) | `run`, `create` |
| `+n` | Host network with extra capabilities | `run`, `create` |
| `+d` | Debug capabilities (`ptrace`, `perfmon`) | `run`, `create` |
| `+?` | Dry run (print the podman command without executing) | all |

Flags can be chained: `+Tdn` gives you terminal, debug, and network.

### Subcommands

Podsock supports the usual `podman` subcommands (`run`, `create`, etc.) plus two helpers:

- **shell** — run an interactive shell (or command) in a running container via `podman exec -it`:
  ```bash
  podsock shell mycontainer        # opens bash
  podsock shell mycontainer python # opens python
  ```

- **helm** — start an existing container via `podman start -ai`, interactively attaching to its entrypoint:
  ```bash
  podsock helm mycontainer
  ```

These added subcommands support the same flags as the podman commands they wrap.

### Examples
(Output from a typical Linux machine, actual output may vary based on your environment)
```bash
podsock run +Twg --rm -it ubuntu bash
# Runs: podman run --interactive --tty --env=TERM=xterm-256color --env=WAYLAND_DISPLAY=wayland-0 --volume=/run/user/1000/wayland-0:/run/user/1000/wayland-0:ro --device /dev/dri --tmpfs /run/user/1000:mode=0700,U --security-opt label=disable --userns keep-id --env=XDG_RUNTIME_DIR=/run/user/1000 --init --rm -it ubuntu bash

podsock run +s --rm -it myimage
# Runs: podman run --env=SSH_AUTH_SOCK=/run/user/1000/ssh-agent.socket --volume=/run/user/1000/ssh-agent.socket:/run/user/1000/ssh-agent.socket:ro --tmpfs /run/user/1000:mode=0700,U --security-opt label=disable --userns keep-id --env=XDG_RUNTIME_DIR=/run/user/1000 --init --rm -it myimage

podsock shell -u root mycontainer
# Runs: podman exec -it -u root mycontainer bash

podsock +? run ubuntu echo hello
# Prints: podman run --tmpfs /run/user/1000:mode=0700,U --security-opt label=disable --userns keep-id --env=XDG_RUNTIME_DIR=/run/user/1000 --init ubuntu echo hello
```

## Installation

To install to `~/.local`:

```bash
make install
```

To install system-wide:

```bash
sudo make install PREFIX=/usr/local
```

Or for packaging with staged install:

```bash
make install PREFIX=/usr DESTDIR=/tmp/podsock-package
```

### Uninstall

```bash
make uninstall  # default prefix
sudo make uninstall PREFIX=/usr/local
```

## Bash Completions and Aliases

The install target automatically installs a bash completion script for `podsock`. It handles `+flag` completion, subcommand mapping, and delegates to `podman`'s own completion engine for the rest.

If you create a bash alias for podsock, you can register completions for it by re-running `make completions` with the `ALIAS` variable:

```bash
# ~/.bashrc
alias pod='podsock'
```

Then run:

```bash
make completions ALIAS=pod
```

This creates a symlink so `pod` gets the same completions as `podsock`.

You can also generate the completion script directly without installing:

```bash
python3 podsock.py --bash-completion
```

## License

This project is licensed under the GNU General Public License v3.0. See the [LICENSE](LICENSE) file for details.
