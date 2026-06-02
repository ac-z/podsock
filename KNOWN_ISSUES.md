# Known Issues

## +D: FileChooser document store unavailable when host uses FUSE

### Description

On Fedora Workstation (and other distros that ship `xdg-document-portal`), the
document store at `/run/user/$UID/doc` is a **FUSE mount** (`fuse.portal`), not a
regular directory.

The kernel denies access to FUSE mounts from any **different** user namespace,
even when the new namespace is a descendant of the one that created the mount.
This is because `xdg-document-portal` mounts the filesystem *without* the
`allow_other` option. The FUSE documentation states:

> `allow_other` restricts access to users in the same userns or a descendant.

Since `allow_other` is not set, only the exact owning user namespace can access
the mount. Rootless containers run in a new user namespace (`--userns keep-id`),
so every bind mount of the document store fails.

crun (Podman's default OCI runtime) exposes this at `podman start` time. It
pre-opens bind-mount sources with `open_tree()` in the host user namespace,
then passes the fd to the container child. The child, now inside the new user
namespace, stats the fd via `/proc/self/fd/<N>` before mounting. FUSE mounts
fail that stat:

```
crun: cannot stat /proc/self/fd/N: Permission denied: OCI permission denied
```

This is **not** a crun-specific bug. It is a general kernel/FUSE/user-namespace
limitation. Other rootless container projects such as **toolbox** and
**distrobox** mount the entire `/run/user/$UID` with `rslave` to avoid the
mount-time error, but runtime access to the FUSE `doc` subdirectory inside the
container still fails with the same permission denied.

### Current behaviour

Podsock detects whether `/run/user/$UID/doc` is a FUSE mount by reading
`/proc/self/mountinfo`. When it is FUSE, podsock **skips** the bind mount and
prints a warning. The container starts normally; portal access over the D-Bus
proxy still works, but the document store is unavailable to the container.

On distros where the doc directory is a plain directory (not FUSE), it is
bind-mounted as usual and the FileChooser portal works fully.

### Who is affected

- **Affected**: Fedora Workstation, RHEL Workstation, and any distro where
  `xdg-document-portal` is running and has mounted the document store.
- **Not affected**: Distros or minimal installations where `/run/user/$UID/doc`
  is a plain directory or does not exist.

### Is there a fix?

Not from podsock's side. Options that have been considered and ruled out:

| Approach | Why it does not help |
|----------|----------------------|
| `chmod 755` on the mount source | The permission denied comes from the kernel denying cross-userns FUSE access, not from file mode bits |
| Pre-creating an empty `/run/user/$UID/doc` directory on the host | The FUSE mount shadowing it still exists; the bind mount would still hit the FUSE filesystem |
| Using a different runtime (runc) | runc avoids crun's `open_tree` path but has other rootless limitations; podman recommends crun for rootless containers |

### What would actually fix it

| Layer | Fix needed |
|-------|-----------|
| **xdg-document-portal** | Mount the document store with `allow_other` (also requires `user_allow_other` in `/etc/fuse.conf`). Firejail developers have independently identified the same requirement ([flatpak/xdg-desktop-portal#741](https://github.com/flatpak/xdg-desktop-portal/pull/741)). |
| **crun** | Detect FUSE bind-mount sources and fall back to the old `mount()` path instead of `open_tree()` + `/proc/self/fd`. |
