#!/usr/bin/env python3
"""Positive control for log mode: proves that a syscall outside the profile is seen.

Takes JRuby's log profile (the profile run_validation.py uses, defaultAction SCMP_ACT_LOG), removes
mkdir and rename from it, runs a JRuby one-liner that makes a directory, writes a file and renames it,
and reads the audit records the same way run_validation.py does. Expected: exactly mkdir and rename,
made by /opt/java/bin/java.

Usage: control/positive_control.py [output.json]      (default control/result.json)
"""
import importlib.util, json, os, sys, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("rv", os.path.join(HERE, "..", "run_validation.py"))
rv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rv)
REMOVE = ["mkdir", "rename"]
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "result.json")

p = json.load(open(rv.log_profile("jruby")))
for r in p["syscalls"]:
    r["names"] = [n for n in r["names"] if n not in REMOVE]
prof = os.path.join(HERE, "jruby_log_minus_mkdir_rename.json")
json.dump(p, open(prof, "w"), indent=1)

name = "wlv-control"
rv.sh(["docker", "rm", "-f", name])
since = time.time()
prog = 'Dir.mkdir("/tmp/c"); File.write("/tmp/c/a", "x"); File.rename("/tmp/c/a", "/tmp/c/b"); puts "done"'
rv.sh(["docker", "run", "-d", "--name", name, "--security-opt", f"seccomp={prof}", rv.APPS["jruby"]["image"],
       "jruby", "-e", prog])
pids, stop = set(), [False]


def poll():
    while not stop[0]:
        pids.update(x for x in rv.sh(["docker", "top", name, "-eo", "pid"]).stdout.split()[1:] if x.isdigit())
        time.sleep(0.2)


threading.Thread(target=poll, daemon=True).start()
rv.sh(["docker", "wait", name])
stop[0] = True
time.sleep(2)
mine, other, raw = rv.denials(since, pids)
res = dict(profile=f"jruby log profile ({rv.profile_path('jruby')}) with {' and '.join(REMOVE)} removed",
           removed=REMOVE, program_output=rv.sh(["docker", "logs", name]).stdout.strip(),
           would_be_denied=mine, unattributed=other, passed=sorted(mine) == sorted(REMOVE))
rv.sh(["docker", "rm", "-f", name])
json.dump(res, open(out, "w"), indent=1)
open(out[:-5] + ".audit.log", "w").write("".join(l + "\n" for l in raw))
print(json.dumps(res, indent=1))
