#!/usr/bin/env python3
"""Who makes the syscalls the profiles miss? Starts <app> under Docker's default profile, waits until it
is started, attaches `strace -f -k` (stack trace per call) to its first process from the host, runs the same workload
as run_validation.py, and writes the stacks to control/strace_<app>.txt.

Usage: trace_callers.py <app> <syscall,...>
"""
import importlib.util, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("rv", f"{HERE}/run_validation.py")
rv = importlib.util.module_from_spec(spec); spec.loader.exec_module(rv)
app, calls = sys.argv[1], sys.argv[2]
a = rv.APPS[app]
name = f"wlv-trace-{app}"
rv.sh(["docker", "rm", "-f", name])
data = rv.prepare()
out = f"{HERE}/control/strace_{app}.txt"
# from start: attach to the container's first process right after docker run (-f follows the JVM it starts)
rv.sh(["docker", "run", "-d", "--name", name, *a["args"], a["image"], *a.get("cmd", [])])
pid = rv.sh(["docker", "inspect", "-f", "{{.State.Pid}}", name]).stdout.strip()
st = subprocess.Popen(["sudo", "-n", "strace", "-f", "-k", "-qq", "-e", f"trace={calls}", "-o", out, "-p", pid])
ip = rv.wait_ready(name, app)
assert ip, "not ready"
time.sleep(3)
c = rv.Count()
rv.globals_ = None
getattr(rv, "wl_" + app)(ip, c, data)
time.sleep(5)
subprocess.run(["sudo", "-n", "kill", "-INT", str(st.pid)])
st.wait()
rv.sh(["docker", "rm", "-f", name])
subprocess.run(["sudo", "-n", "chown", f"{os.getuid()}", out])
print(app, "ops ok", c.ok, "failed", c.fail, "->", out)
