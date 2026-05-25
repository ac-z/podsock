#!/usr/bin/env python3
import subprocess
import sys
import os

tests = [
    # ---- Basic dispatch ----
    (["+?", "run", "myimage"], "success", ["podman", "run", "--tmpfs", "myimage"]),
    (["+?t", "run", "myimage"], "success", ["podman", "run", "--interactive", "--tty", "myimage"]),
    (["+?", "shell", "mycontainer"], "success", ["podman", "exec", "-it", "mycontainer", "bash"]),
    (["+?", "helm", "mycontainer"], "success", ["podman", "start", "-ai", "mycontainer"]),

    # ---- Edge cases ----
    (["+?"], "success", ["podman"]),
    (["+?x", "run", "myimage"], "error", ["not supported"]),
    (["+t", "shell", "mycontainer"], "error", ["not supported"]),

    # ---- Passthrough / other subcommands ----
    (["+?", "ps"], "success", ["podman", "ps"]),
    (["+?", "exec", "mycontainer", "ls"], "success", ["podman", "exec", "mycontainer", "ls"]),
    (["+?", "logs", "mycontainer"], "success", ["podman", "logs", "mycontainer"]),

    # ---- Flags before and after subcommand ----
    (["+?", "+t", "run", "myimage"], "success", ["--interactive", "--tty", "myimage"]),
    (["run", "+?", "myimage"], "success", ["podman", "run", "--tmpfs", "myimage"]),
    (["+?", "create", "myimage"], "success", ["podman", "create", "myimage"]),
    # Flags after subcommand expand (using +Tngd to avoid w/s socket checks)
    (["+?", "create", "--name", "test", "+Tngd", "imagename"], "success", ["create", "--interactive", "--tty", "--network=host", "--cap-add=NET_RAW,NET_ADMIN,NET_BIND_SERVICE", "--cap-add=SYS_PTRACE,PERFMON", "--name", "test", "imagename"]),
    (["create", "--name", "test", "+Tngd?", "imagename"], "success", ["create", "--interactive", "--tty", "--network=host", "--cap-add=NET_RAW,NET_ADMIN,NET_BIND_SERVICE", "--cap-add=SYS_PTRACE,PERFMON", "--name", "test", "imagename"]),

    # ---- Bash completion ----
    (["--bash-completion"], "success", ["_podsock", "complete -o default -F _podsock podsock"]),

    # ---- Help ----
    (["+?", "run", "--help"], "help", ["Podsock", "Available +flags"]),

    # ---- Options and positional args ----
    (["+?", "run", "myimage", "-p", "8080:80"], "success", ["-p", "8080:80"]),
    (["+?", "shell", "mycontainer", "sh", "-c", "echo hi"], "success", ["podman", "exec", "-it", "mycontainer", "sh", "-c", "echo hi"]),
    (["+?", "helm", "mycontainer", "extra"], "success", ["podman", "start", "-ai", "mycontainer"]),
    (["+?", "shell", "--user", "root", "mycontainer"], "success", ["podman", "exec", "-it", "--user", "root", "mycontainer", "bash"]),
    (["+?", "shell", "--workdir", "/tmp", "mycontainer", "sh"], "success", ["podman", "exec", "-it", "--workdir", "/tmp", "mycontainer", "sh"]),
    (["+?", "helm", "--attach", "mycontainer"], "success", ["podman", "start", "-ai", "--attach", "mycontainer"]),

    # ---- Double-dash literal passthrough ----
    (["+?", "run", "myimage", "--", "echo", "+hello"], "success", ["--", "echo", "+hello"]),
    # +extra after image is a flag; use -- for literal +args
    (["+?", "run", "myimage", "+extra"], "error", ["not supported"]),
    (["+?", "run", "myimage", "--", "+extra"], "success", ["--", "+extra"]),
]

env = {"PATH": "/tmp/fakebin:" + subprocess.check_output(["bash", "-c", "echo $PATH"]).decode().strip()}

passed = 0
failed = 0

for args, behavior, expected in tests:
    # ---- Run test ----
    result = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), "podsock.py")] + args,
        capture_output=True, text=True, env=env, check=False,
    )
    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    combined = stdout + "\n" + stderr

    # ---- Evaluate ----
    if behavior == "error":
        if result.returncode != 0:
            missing = [s for s in expected if s not in combined]
            if not missing:
                passed += 1
                print(f"PASS [{args}]")
            else:
                failed += 1
                print(f"FAIL [{args}]: missing {missing} in {combined!r}")
        else:
            failed += 1
            print(f"FAIL [{args}]: expected error, got rc=0 out={stdout!r} err={stderr!r}")
    elif behavior == "help":
        if result.returncode == 0:
            missing = [s for s in expected if s not in combined]
            if not missing:
                passed += 1
                print(f"PASS [{args}]")
            else:
                failed += 1
                print(f"FAIL [{args}]: missing {missing} in {combined!r}")
        else:
            failed += 1
            print(f"FAIL [{args}]: expected help success, got rc={result.returncode}")
    else:
        if result.returncode != 0:
            failed += 1
            print(f"FAIL [{args}]: rc={result.returncode} err={stderr!r}")
            continue
        missing = [s for s in expected if s not in stdout]
        if missing:
            failed += 1
            print(f"FAIL [{args}]: missing {missing} in {stdout!r}")
        else:
            passed += 1
            print(f"PASS [{args}]")

# ---- Bash completion functional tests ----
completion_script = subprocess.check_output(
    [sys.executable, os.path.join(os.path.dirname(__file__), "podsock.py"), "--bash-completion"]
).decode()

bash_test = '''
set -e

# compopt doesn't work outside a real completion function
compopt() { :; }

# Mock podman that responds to __complete
podman() {
    if [[ "$1" != "__complete" ]]; then
        echo "fake: unexpected podman call" >&2; return 1
    fi
    shift
    local a1="$1" a2="$2" a3="$3"
    if [[ $# -eq 1 && -z "$a1" ]]; then
        # podman __complete ''
        echo -e "run\nexec\ncreate\nps\n:4"
    elif [[ "$a1" == "run" && $# -eq 2 && -z "$a2" ]]; then
        # podman __complete run ''
        echo -e "--interactive\n--name\n--rm\n--tty\n:4"
    elif [[ "$a1" == "exec" && $# -eq 2 && -z "$a2" ]]; then
        # podman __complete exec '' (mapped from shell)
        echo -e "--user\n--workdir\n--tty\n:4"
    elif [[ "$a1" == "start" && $# -eq 2 && -z "$a2" ]]; then
        # podman __complete start '' (mapped from helm)
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

''' + completion_script + '''
test_flags() {
    COMP_WORDS=("$@")
    COMP_CWORD=$(($# - 1))
    _podsock
    echo "${COMPREPLY[*]}"
}

# run +flags
out=$(test_flags podsock run "+")
[[ "$out" == *"+t"* ]] || { echo "FAIL: run +flag missing +t got: $out"; exit 1; }
[[ "$out" == *"+?"* ]] || { echo "FAIL: run +flag missing +? got: $out"; exit 1; }

# shell +flags (only +?)
out=$(test_flags podsock shell "+")
[[ "$out" != *"+t"* ]] || { echo "FAIL: shell +flag has +t got: $out"; exit 1; }
[[ "$out" == *"+?"* ]] || { echo "FAIL: shell +flag missing +? got: $out"; exit 1; }

# create +flags
out=$(test_flags podsock create "+")
[[ "$out" == *"+w"* ]] || { echo "FAIL: create +flag missing +w got: $out"; exit 1; }

# no subcommand yet
out=$(test_flags podsock "+")
[[ "$out" == *"+?"* ]] || { echo "FAIL: nosub +flag missing +? got: $out"; exit 1; }
[[ "$out" != *"+t"* ]] || { echo "FAIL: nosub +flag has +t got: $out"; exit 1; }

# exact match
out=$(test_flags podsock run "+t")
[[ "$out" == "+t" ]] || { echo "FAIL: exact +t got: $out"; exit 1; }

# podman __complete '' (empty args → subcommands)
out=$(test_flags podsock "")
[[ "$out" == *"run"* ]] || { echo "FAIL: subcommands missing 'run' got: $out"; exit 1; }
[[ "$out" == *"exec"* ]] || { echo "FAIL: subcommands missing 'exec' got: $out"; exit 1; }

# podman __complete run '' (run options)
out=$(test_flags podsock run "")
[[ "$out" == *"--interactive"* ]] || { echo "FAIL: run options missing '--interactive' got: $out"; exit 1; }
[[ "$out" == *"--name"* ]] || { echo "FAIL: run options missing '--name' got: $out"; exit 1; }

# podman __complete exec '' (shell mapped to exec)
out=$(test_flags podsock shell "")
[[ "$out" == *"--user"* ]] || { echo "FAIL: shell(exec) options missing '--user' got: $out"; exit 1; }

# podman __complete start '' (helm mapped to start)
out=$(test_flags podsock helm "")
[[ "$out" == *"--attach"* ]] || { echo "FAIL: helm(start) options missing '--attach' got: $out"; exit 1; }

# podman __complete ru (partial subcommand)
out=$(test_flags podsock ru)
[[ "$out" == "run" ]] || { echo "FAIL: partial 'ru' should give 'run' got: $out"; exit 1; }

# podman __complete run --name (flag completion)
out=$(test_flags podsock run --name)
[[ "$out" == "--name" ]] || { echo "FAIL: flag '--name' expected got: $out"; exit 1; }

# podman __complete run --name= '' (flag value after =)
out=$(test_flags podsock run "--name=" "")
[[ "$out" == *"myimage"* ]] || { echo "FAIL: flag value missing 'myimage' got: $out"; exit 1; }

# podman __complete run --name=myi (flag value with prefix, strip --name=)
out=$(test_flags podsock run "--name=myi")
[[ "$out" == *"myimage"* ]] || { echo "FAIL: flag value prefix strip missing 'myimage' got: $out"; exit 1; }

# +flag stripped before delegation
out=$(test_flags podsock "+t" run "")
[[ "$out" == *"--interactive"* ]] || { echo "FAIL: +t strip before delegate missing '--interactive' got: $out"; exit 1; }

echo "BASH_PASS"
'''

result = subprocess.run(["bash", "-c", bash_test], capture_output=True, text=True, check=False)
if result.returncode == 0 and result.stdout.strip() == "BASH_PASS":
    passed += 1
    print("PASS [bash completion]")
else:
    failed += 1
    print(f"FAIL [bash completion]: rc={result.returncode} out={result.stdout.strip()!r} err={result.stderr.strip()!r}")

print(f"\n{passed} passed, {failed} failed")
