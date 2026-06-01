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
import subprocess
import sys

import pytest

PODSOCK = os.path.join(os.path.dirname(__file__), "podsock.py")
_ENV = {
    "PATH": "/tmp/fakebin:" + subprocess.check_output(["bash", "-c", "echo $PATH"]).decode().strip(),
    "TERM": os.environ.get("TERM", "xterm"),
}
PODSOCK_RTDIR = f"/run/user/{os.getuid()}"
TERM = os.environ.get("TERM", "xterm")

_RUN_OPTS = ["--tmpfs", f"{PODSOCK_RTDIR}:mode=0700,U", "--security-opt", "label=disable", "--userns", "keep-id", f"--env=XDG_RUNTIME_DIR={PODSOCK_RTDIR}", "--init"]
_CREATE_OPTS = ["--tmpfs", f"{PODSOCK_RTDIR}:mode=0700,U", "--security-opt", "label=disable", "--userns", "keep-id", f"--env=XDG_RUNTIME_DIR={PODSOCK_RTDIR}", "--init"]
_T = ["--interactive", "--tty", f"--env=TERM={TERM}"]
_TT = ["--interactive", "--tty", "--env=TERM=xterm-256color"]
_N = ["--network=host", "--cap-add=NET_RAW,NET_ADMIN,NET_BIND_SERVICE"]
_D = ["--cap-add=SYS_PTRACE,PERFMON", "--security-opt", "seccomp=unconfined"]


def _run(args, env=None):
    env = env or _ENV
    return subprocess.run(
        [sys.executable, PODSOCK] + args,
        capture_output=True, text=True, env=env, check=False,
    )


def _cmd_from_dryrun(stdout):
    line = stdout.strip()
    return shlex.split(line) if line else []


_A_LABELS = ["--label=podsock.app_id=podsock_myapp", "--label=podsock.name=myapp"]
_D_LABELS = ["--label=podsock.portal=true"]
_PROXY_HOST_DIR = os.path.expanduser("~/.var/podsock/sockets/myapp")
_D_PORTAL = [
    f"--env=DBUS_SESSION_BUS_ADDRESS=unix:path={PODSOCK_RTDIR}/podsock_proxy/bus.sock",
    f"--volume={_PROXY_HOST_DIR}:{PODSOCK_RTDIR}/podsock_proxy:ro",
    f"--volume={PODSOCK_RTDIR}/doc:{PODSOCK_RTDIR}/doc",
]

_DRYRUN_CASES = [
    (["+?", "run", "myimage"], ["podman", "run"] + _RUN_OPTS + ["myimage"]),
    (["+?t", "run", "myimage"], ["podman", "run"] + _T + _RUN_OPTS + ["myimage"]),
    (["+?", "shell", "mycontainer"], ["podman", "exec", "-it", "mycontainer", "bash"]),
    (["+?", "helm", "mycontainer"], ["podman", "start", "-ai", "mycontainer"]),
    (["+?"], ["podman"]),
    (["+?", "ps"], ["podman", "ps"]),
    (["+?", "exec", "mycontainer", "ls"], ["podman", "exec", "mycontainer", "ls"]),
    (["+?", "logs", "mycontainer"], ["podman", "logs", "mycontainer"]),
    (["+?", "+t", "run", "myimage"], ["podman", "run"] + _T + _RUN_OPTS + ["myimage"]),
    (["run", "+?", "myimage"], ["podman", "run"] + _RUN_OPTS + ["myimage"]),
    (["+?", "create", "myimage"], ["podman", "create"] + _CREATE_OPTS + ["myimage"]),
    (
        ["+?", "create", "--name", "test", "+Tngd", "imagename"],
        ["podman", "create"] + _TT + _N + ["--device", "/dev/dri"] + _D + _CREATE_OPTS + ["--name", "test", "imagename"],
    ),
    (
        ["create", "--name", "test", "+Tngd?", "imagename"],
        ["podman", "create"] + _TT + _N + ["--device", "/dev/dri"] + _D + _CREATE_OPTS + ["--name", "test", "imagename"],
    ),
    (["+?", "run", "myimage", "-p", "8080:80"], ["podman", "run"] + _RUN_OPTS + ["myimage", "-p", "8080:80"]),
    (["+?", "shell", "mycontainer", "sh", "-c", "echo hi"], ["podman", "exec", "-it", "mycontainer", "sh", "-c", "echo hi"]),
    (["+?", "helm", "mycontainer", "extra"], ["podman", "start", "-ai", "mycontainer", "extra"]),
    (["+?", "shell", "--user", "root", "mycontainer"], ["podman", "exec", "-it", "--user", "root", "mycontainer", "bash"]),
    (["+?", "shell", "--workdir", "/tmp", "mycontainer", "sh"], ["podman", "exec", "-it", "--workdir", "/tmp", "mycontainer", "sh"]),
    (["+?", "helm", "--attach", "mycontainer"], ["podman", "start", "-ai", "--attach", "mycontainer"]),
    (["+?", "run", "myimage", "--", "echo", "+hello"], ["podman", "run"] + _RUN_OPTS + ["myimage", "--", "echo", "+hello"]),
    (["+?", "run", "myimage", "--", "+extra"], ["podman", "run"] + _RUN_OPTS + ["myimage", "--", "+extra"]),
    (["+?", "shell", "-u", "root", "mycontainer"], ["podman", "exec", "-it", "-u", "root", "mycontainer", "bash"]),
    (["+?", "shell", "-w", "/tmp", "mycontainer"], ["podman", "exec", "-it", "-w", "/tmp", "mycontainer", "bash"]),
    (["+?", "run", "myimage", "--", "-h"], ["podman", "run"] + _RUN_OPTS + ["myimage", "--", "-h"]),
    (["+?", "run", "myimage", "--", "--help"], ["podman", "run"] + _RUN_OPTS + ["myimage", "--", "--help"]),
    (["+?A", "run", "--name=myapp", "myimage"], ["podman", "run"] + _RUN_OPTS + _A_LABELS + ["--name=myapp", "myimage"]),
    (["+?D", "run", "--name=myapp", "myimage"], ["podman", "run"] + _RUN_OPTS + _A_LABELS + _D_LABELS + _D_PORTAL + ["--name=myapp", "myimage"]),
    (["+?AD", "run", "--name=myapp", "myimage"], ["podman", "run"] + _RUN_OPTS + _A_LABELS + _D_LABELS + _D_PORTAL + ["--name=myapp", "myimage"]),
    (["+?A", "create", "--name=myapp", "myimage"], ["podman", "create"] + _CREATE_OPTS + _A_LABELS + ["--name=myapp", "myimage"]),
    (["+?D", "create", "--name=myapp", "myimage"], ["podman", "create"] + _CREATE_OPTS + _A_LABELS + _D_LABELS + _D_PORTAL + ["--name=myapp", "myimage"]),
]


# ---- Dry-run exact assertions ----
@pytest.mark.parametrize(
    "args,expected",
    _DRYRUN_CASES,
    ids=[" ".join(c[0]) for c in _DRYRUN_CASES],
)
def test_dryrun(args, expected):
    result = _run(args)
    assert result.returncode == 0, result.stderr
    assert _cmd_from_dryrun(result.stdout) == expected


_ERROR_CASES = [
    (["+?x", "run", "myimage"], ["not supported"]),
    (["+t", "shell", "mycontainer"], ["not supported"]),
    (["+tT", "run", "myimage"], ["mutually exclusive"]),
    (["+t", "+T", "run", "myimage"], ["mutually exclusive"]),
    (["+T", "+t", "run", "myimage"], ["mutually exclusive"]),
    (["+?", "run", "myimage", "+extra"], ["not supported"]),
    (["+A", "shell", "mycontainer"], ["not supported"]),
    (["+D", "helm", "mycontainer"], ["not supported"]),
]


# ---- Error cases ----
@pytest.mark.parametrize(
    "args,expected_substrings",
    _ERROR_CASES,
    ids=[" ".join(c[0]) for c in _ERROR_CASES],
)
def test_error(args, expected_substrings):
    result = _run(args)
    assert result.returncode != 0
    combined = result.stdout + "\n" + result.stderr
    for s in expected_substrings:
        assert s in combined


_HELP_CASES = [
    (["+?", "run", "--help"], ["Podsock", "Available +flags", "WARNING"]),
    (["+?", "run", "-h", "myimage"], ["Podsock"]),
    (["+?", "run", "--help", "myimage"], ["Podsock"]),
    (["+?", "create", "--help"], ["WARNING", "portal"]),
]


# ---- Help cases ----
@pytest.mark.parametrize(
    "args,expected_substrings",
    _HELP_CASES,
    ids=[" ".join(c[0]) for c in _HELP_CASES],
)
def test_help(args, expected_substrings):
    result = _run(args)
    assert result.returncode == 0
    combined = result.stdout + "\n" + result.stderr
    for s in expected_substrings:
        assert s in combined


# ---- Bash completion output ----
def test_bash_completion_output():
    result = _run(["--bash-completion"])
    assert result.returncode == 0
    assert "_podsock" in result.stdout
    assert 'complete -o default -F _podsock "${BASH_SOURCE##*/}"' in result.stdout


# ---- Bash completion functional tests ----
COMPLETION_SCRIPT = subprocess.check_output([sys.executable, PODSOCK, "--bash-completion"]).decode()

MOCK_PODMAN = r'''
podman() {
    if [[ "$1" != "__complete" ]]; then
        echo "fake: unexpected podman call" >&2; return 1
    fi
    shift
    local a1="$1" a2="$2" a3="$3"
    if [[ $# -eq 1 && -z "$a1" ]]; then
        echo -e "run\nexec\ncreate\nps\n:4"
    elif [[ "$a1" == "run" && $# -eq 2 && -z "$a2" ]]; then
        echo -e "--interactive\n--name\n--rm\n--tty\n:4"
    elif [[ "$a1" == "exec" && $# -eq 2 && -z "$a2" ]]; then
        echo -e "--user\n--workdir\n--tty\n:4"
    elif [[ "$a1" == "start" && $# -eq 2 && -z "$a2" ]]; then
        echo -e "--attach\n--interactive\n:4"
    elif [[ "$a1" == "stop" && $# -eq 2 && -z "$a2" ]]; then
        echo -e "mycontainer\nshell\nhelm\n:4"
    elif [[ "$a1" == "ru" && $# -eq 1 ]]; then
        echo -e "run\n:0"
    elif [[ "$a1" == "run" && "$a2" == "--name" && $# -eq 2 ]]; then
        echo -e "--name\tset a name\n:4"
    elif [[ "$a1" == "run" && "$a2" == "--name=" && $# -eq 3 && -z "$a3" ]]; then
        echo -e "myimage\nmyother\n:4"
    elif [[ "$a1" == "run" && "$a2" == "--name=myi" && $# -eq 2 ]]; then
        echo -e "--name=myimage\n--name=myother\n:4"
    else
        echo -e ":0"
    fi
}
'''


def _bash_complete(words):
    quoted = " ".join(shlex.quote(w) for w in words)
    bash_code = f'''compopt() {{ :; }}
{MOCK_PODMAN}
{COMPLETION_SCRIPT}
COMP_WORDS=({quoted})
COMP_CWORD={len(words) - 1}
_podsock
echo "${{COMPREPLY[*]}}"
'''
    result = subprocess.run(["bash", "-c", bash_code], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


class TestBashCompletionFlags:
    def test_run_plusflags(self):
        out = _bash_complete(["podsock", "run", "+"])
        assert "+t" in out
        assert "+?" in out

    def test_shell_plusflags(self):
        out = _bash_complete(["podsock", "shell", "+"])
        assert "+t" not in out
        assert "+?" in out

    def test_create_plusflags(self):
        out = _bash_complete(["podsock", "create", "+"])
        assert "+w" in out

    def test_nosub_plusflags(self):
        out = _bash_complete(["podsock", "+"])
        assert "+?" in out
        assert "+t" not in out

    def test_chained_no_resuggest(self):
        out = _bash_complete(["podsock", "run", "+t"])
        assert "+tt" not in out
        assert "+tw" in out
        assert "+ts" in out

    def test_chained_multi_no_resuggest(self):
        out = _bash_complete(["podsock", "run", "+Td"])
        assert "+TdT" not in out
        assert "+Tdd" not in out
        assert "+Tdw" in out

    def test_chained_preserves_prefix(self):
        out = _bash_complete(["podsock", "run", "+Twd"])
        assert "+Twds" in out
        assert "+Twdg" in out
        for w in out.split():
            assert w.startswith("+Twd"), f"completion {w!r} lost prefix in {out!r}"

    def test_mutually_exclusive_tT(self):
        out = _bash_complete(["podsock", "run", "+t"])
        assert "+tT" not in out
        out = _bash_complete(["podsock", "run", "+T"])
        assert "+Tt" not in out
        out = _bash_complete(["podsock", "+t", "run", "+"])
        assert "+T" not in out

    def test_multiword_dedup(self):
        out = _bash_complete(["podsock", "+T", "+d", "run", "+"])
        assert "+T" not in out
        assert "+d" not in out
        assert "+w" in out


# ---- App ID generation ----
class TestAppId:
    def test_simple_name(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("podsock", PODSOCK)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert mod._generate_app_id("myapp") == "podsock_myapp"

    def test_hyphen_replaced(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("podsock", PODSOCK)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert mod._generate_app_id("my-app") == "podsock_my_app"

    def test_digit_prefix(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("podsock", PODSOCK)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert mod._generate_app_id("123app") == "podsock_x123app"

    def test_empty_name(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("podsock", PODSOCK)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        app_id = mod._generate_app_id("")
        assert app_id.startswith("podsock_")
        assert len(app_id) == len("podsock_") + 8

    def test_long_name_truncated(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("podsock", PODSOCK)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        long_name = "a" * 300
        app_id = mod._generate_app_id(long_name)
        assert len(app_id) <= 255


# ---- Desktop file creation ----
class TestDesktopFile:
    def test_create_and_delete(self, tmp_path):
        import importlib.util
        spec = importlib.util.spec_from_file_location("podsock", PODSOCK)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        # Override desktop dir to use tmp_path
        original_dir = mod._DESKTOP_DIR
        mod._DESKTOP_DIR = str(tmp_path)
        try:
            mod._create_desktop_file("podsock_myapp", "myapp", dryrun=False)
            path = mod._desktop_file_path("podsock_myapp")
            assert os.path.exists(path)
            with open(path, "r", encoding="utf-8") as f:
                contents = f.read()
            assert "Podsock Container: myapp" in contents
            assert "Exec=podsock helm --name=myapp" in contents
            # Idempotent: second call should not fail
            mod._create_desktop_file("podsock_myapp", "myapp", dryrun=False)
            mod._delete_desktop_file("podsock_myapp")
            assert not os.path.exists(path)
        finally:
            mod._DESKTOP_DIR = original_dir

    def test_dryrun_noop(self, tmp_path):
        import importlib.util
        spec = importlib.util.spec_from_file_location("podsock", PODSOCK)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        original_dir = mod._DESKTOP_DIR
        mod._DESKTOP_DIR = str(tmp_path)
        try:
            mod._create_desktop_file("podsock_myapp", "myapp", dryrun=True)
            path = mod._desktop_file_path("podsock_myapp")
            assert not os.path.exists(path)
        finally:
            mod._DESKTOP_DIR = original_dir


# ---- Portal flag error conditions ----
class TestPortalErrors:
    def test_dbus_address_missing(self):
        env = dict(_ENV)
        env.pop("DBUS_SESSION_BUS_ADDRESS", None)
        result = _run(["+D", "run", "--name=myapp", "myimage"], env=env)
        assert result.returncode != 0
        combined = result.stdout + "\n" + result.stderr
        assert "DBUS_SESSION_BUS_ADDRESS" in combined

    def test_dbus_address_not_unix(self):
        env = dict(_ENV)
        env["DBUS_SESSION_BUS_ADDRESS"] = "tcp:host=127.0.0.1"
        result = _run(["+D", "run", "--name=myapp", "myimage"], env=env)
        assert result.returncode != 0
        combined = result.stdout + "\n" + result.stderr
        assert "unix socket" in combined or "not a unix socket" in combined


# ---- Utility helpers ----
class TestHelpers:
    def test_extract_container_name_equals(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("podsock", PODSOCK)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert mod._extract_container_name(["--name=foo", "other"]) == "foo"

    def test_extract_container_name_space(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("podsock", PODSOCK)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert mod._extract_container_name(["--name", "foo", "other"]) == "foo"

    def test_extract_container_name_missing(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("podsock", PODSOCK)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert mod._extract_container_name(["run", "myimage"]) is None

    def test_stop_proxy_keeps_dir_by_default(self, tmp_path):
        import importlib.util
        spec = importlib.util.spec_from_file_location("podsock", PODSOCK)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        original_rtdir = mod.PODSOCK_RTDIR
        mod.PODSOCK_RTDIR = str(tmp_path)
        try:
            socket_dir = mod._proxy_socket_dir("myapp")
            os.makedirs(socket_dir, exist_ok=True)
            pid_file = os.path.join(socket_dir, "proxy.pid")
            with open(pid_file, "w") as f:
                f.write("999999\n")
            mod._stop_xdg_dbus_proxy("podsock_myapp", "myapp")
            # Directory must survive so podman mount stays valid
            assert os.path.exists(socket_dir)
            assert not os.path.exists(pid_file)
        finally:
            mod.PODSOCK_RTDIR = original_rtdir

    def test_stop_proxy_removes_dir_when_asked(self, tmp_path):
        import importlib.util
        spec = importlib.util.spec_from_file_location("podsock", PODSOCK)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        original_rtdir = mod.PODSOCK_RTDIR
        mod.PODSOCK_RTDIR = str(tmp_path)
        try:
            socket_dir = mod._proxy_socket_dir("myapp")
            os.makedirs(socket_dir, exist_ok=True)
            pid_file = os.path.join(socket_dir, "proxy.pid")
            with open(pid_file, "w") as f:
                f.write("999999\n")
            mod._stop_xdg_dbus_proxy("podsock_myapp", "myapp", remove_dir=True)
            assert not os.path.exists(socket_dir)
        finally:
            mod.PODSOCK_RTDIR = original_rtdir


# ---- Bash completion includes A and D ----
class TestBashCompletionPortalFlags:
    def test_run_includes_A(self):
        out = _bash_complete(["podsock", "run", "+"])
        assert "+A" in out

    def test_run_includes_D(self):
        out = _bash_complete(["podsock", "run", "+"])
        assert "+D" in out

    def test_create_includes_D(self):
        out = _bash_complete(["podsock", "create", "+"])
        assert "+D" in out

    def test_shell_excludes_D(self):
        out = _bash_complete(["podsock", "shell", "+"])
        assert "+D" not in out


class TestBashCompletionPodmanDelegation:
    def test_subcommands(self):
        out = _bash_complete(["podsock", ""])
        assert "run" in out
        assert "exec" in out
        assert "shell" in out
        assert "helm" in out

    def test_run_options(self):
        out = _bash_complete(["podsock", "run", ""])
        assert "--interactive" in out
        assert "--name" in out

    def test_shell_mapped_to_exec(self):
        out = _bash_complete(["podsock", "shell", ""])
        assert "--user" in out

    def test_helm_mapped_to_start(self):
        out = _bash_complete(["podsock", "helm", ""])
        assert "--attach" in out

    def test_partial_subcommand(self):
        out = _bash_complete(["podsock", "ru"])
        assert out == "run"

    def test_flag_completion(self):
        out = _bash_complete(["podsock", "run", "--name"])
        assert out == "--name"

    def test_flag_value_after_equals(self):
        out = _bash_complete(["podsock", "run", "--name=", ""])
        assert "myimage" in out

    def test_flag_value_with_prefix(self):
        out = _bash_complete(["podsock", "run", "--name=myi"])
        assert "myimage" in out

    def test_plusflag_stripped_before_delegate(self):
        out = _bash_complete(["podsock", "+t", "run", ""])
        assert "--interactive" in out

    def test_no_shell_helm_in_container_lists(self):
        # podman stop returns container names; shell/helm should not be injected
        out = _bash_complete(["podsock", "stop", ""])
        assert "mycontainer" in out
        # "shell" and "helm" are container names from podman, not injected subcommands
        # but we verify they only appear once (from podman) and that no extra injection happens
        # The real check: shell/helm should NOT be added as subcommand completions here
        words = out.split()
        assert words.count("shell") == 1
        assert words.count("helm") == 1
        assert "mycontainer" in words
