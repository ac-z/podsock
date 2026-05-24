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


# ---- Dry-run exact assertions ----
@pytest.mark.parametrize(
    "args,expected",
    [
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
    ],
    ids=lambda kv: "-".join(kv[0]) if kv else "",
)
def test_dryrun(args, expected):
    result = _run(args)
    assert result.returncode == 0, result.stderr
    assert _cmd_from_dryrun(result.stdout) == expected


# ---- Error cases ----
@pytest.mark.parametrize(
    "args,expected_substrings",
    [
        (["+?x", "run", "myimage"], ["not supported"]),
        (["+t", "shell", "mycontainer"], ["not supported"]),
        (["+tT", "run", "myimage"], ["mutually exclusive"]),
        (["+t", "+T", "run", "myimage"], ["mutually exclusive"]),
        (["+T", "+t", "run", "myimage"], ["mutually exclusive"]),
        (["+?", "run", "myimage", "+extra"], ["not supported"]),
    ],
    ids=lambda kv: " ".join(kv[0]) if kv else "",
)
def test_error(args, expected_substrings):
    result = _run(args)
    assert result.returncode != 0
    combined = result.stdout + "\n" + result.stderr
    for s in expected_substrings:
        assert s in combined


# ---- Help cases ----
@pytest.mark.parametrize(
    "args,expected_substrings",
    [
        (["+?", "run", "--help"], ["Podsock", "Available +flags"]),
        (["+?", "run", "-h", "myimage"], ["Podsock"]),
        (["+?", "run", "--help", "myimage"], ["Podsock"]),
    ],
    ids=lambda kv: " ".join(kv[0]) if kv else "",
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
    assert "complete -o default -F _podsock podsock" in result.stdout


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
