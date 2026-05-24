#!/usr/bin/env python3
import subprocess
import sys

tests = [
    (["+?", "run", "myimage"], "success", ["podman", "run", "--tmpfs", "myimage"]),
    (["+?t", "run", "myimage"], "success", ["podman", "run", "--interactive", "--tty", "myimage"]),
    (["+?", "shell", "mycontainer"], "success", ["podman", "exec", "-it", "mycontainer", "bash"]),
    (["+?", "helm", "mycontainer"], "success", ["podman", "start", "-ai", "mycontainer"]),
    (["+t", "shell", "mycontainer"], "error", ["not supported"]),
    (["+?"], "success", ["podman"]),
    (["+?", "run", "myimage", "--", "echo", "+hello"], "success", ["--", "echo", "+hello"]),
    (["+?", "+t", "run", "myimage"], "success", ["--interactive", "--tty", "myimage"]),
    (["+?x", "run", "myimage"], "error", ["not supported"]),
    (["+?", "ps"], "success", ["podman", "ps"]),
    # +? after subcommand is consumed as dry-run flag, not passed through
    (["run", "+?", "myimage"], "success", ["podman", "run", "--tmpfs", "myimage"]),
    (["+?", "create", "myimage"], "success", ["podman", "create", "myimage"]),
    (["+?", "run", "--help"], "help", ["Podsock", "Available +flags"]),
    (["+?", "run", "myimage", "-p", "8080:80"], "success", ["-p", "8080:80"]),
    (["+?", "exec", "mycontainer", "ls"], "success", ["podman", "exec", "mycontainer", "ls"]),
    (["+?", "logs", "mycontainer"], "success", ["podman", "logs", "mycontainer"]),
    (["+?", "shell", "mycontainer", "sh", "-c", "echo hi"], "success", ["podman", "exec", "-it", "mycontainer", "sh", "-c", "echo hi"]),
    (["+?", "helm", "mycontainer", "extra"], "success", ["podman", "start", "-ai", "mycontainer"]),
    (["+?", "shell", "--user", "root", "mycontainer"], "success", ["podman", "exec", "-it", "--user", "root", "mycontainer", "bash"]),
    (["+?", "shell", "--workdir", "/tmp", "mycontainer", "sh"], "success", ["podman", "exec", "-it", "--workdir", "/tmp", "mycontainer", "sh"]),
    (["+?", "helm", "--attach", "mycontainer"], "success", ["podman", "start", "-ai", "--attach", "mycontainer"]),
    # +extra after image is a flag; use -- for literal +args
    (["+?", "run", "myimage", "+extra"], "error", ["not supported"]),
    (["+?", "run", "myimage", "--", "+extra"], "success", ["--", "+extra"]),
    # Flags after subcommand expand (using +Tngd to avoid w/s socket checks)
    (["+?", "create", "--name", "test", "+Tngd", "imagename"], "success", ["create", "--interactive", "--tty", "--network=host", "--cap-add=NET_RAW,NET_ADMIN,NET_BIND_SERVICE", "--cap-add=SYS_PTRACE,PERFMON", "--name", "test", "imagename"]),
    (["create", "--name", "test", "+Tngd?", "imagename"], "success", ["create", "--interactive", "--tty", "--network=host", "--cap-add=NET_RAW,NET_ADMIN,NET_BIND_SERVICE", "--cap-add=SYS_PTRACE,PERFMON", "--name", "test", "imagename"]),
]

env = {"PATH": "/tmp/fakebin:" + subprocess.check_output(["bash", "-c", "echo $PATH"]).decode().strip()}

passed = 0
failed = 0

for args, behavior, expected in tests:
    result = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), "podsock.py")] + args,
        capture_output=True, text=True, env=env, check=False,
    )
    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    combined = stdout + "\n" + stderr
    
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

print(f"\n{passed} passed, {failed} failed")
