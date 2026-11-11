#!/usr/bin/env python3
"""Raw SECCOMP audit records for log runs made before run_validation.py saved them itself.

For each <results>/<app>/log_<rep>.json without a log_<rep>.audit.log, writes the SCMP_ACT_LOG records
(type=SECCOMP, code=0x7ffc0000) of /var/log/audit/audit.log* inside the run's time window: from the
container's start (JSON written at the end, minus ready time and workload time, minus 30 s) to the JSON's
write time. Apps ran in parallel, so records of another app in log mode at the same time can fall in the
window. Such a record is prefixed "# other app: " when its syscall is not in this run's would_be_denied
(the per-PID attribution made during the run); a record whose syscall is in it is kept as is.

Usage: extract_audit_records.py <results dir> [...]   (needs sudo to read the audit log)
"""
import glob, json, os, re, subprocess, sys

raw = subprocess.run(["sudo", "-n", "sh", "-c", "cat /var/log/audit/audit.log.[4321] /var/log/audit/audit.log 2>/dev/null"],
                     capture_output=True, text=True).stdout
recs = [(float(re.search(r"audit\((\d+\.\d+):", l).group(1)), l) for l in raw.splitlines()
        if "type=SECCOMP" in l and "code=0x7ffc0000" in l]
names = {}


def name(nr):
    if nr not in names:
        names[nr] = subprocess.run(["ausyscall", "x86_64", nr], capture_output=True, text=True).stdout.strip() or nr
    return names[nr]


for d in sys.argv[1:]:
    for j in sorted(glob.glob(f"{d}/*/log_*.json")):
        out = j[:-5] + ".audit.log"
        if os.path.exists(out):
            continue
        r = json.load(open(j))
        end = os.path.getmtime(j)
        start = end - r.get("ready_after_s", 0) - (r.get("workload_s") or 0) - 30
        mine = set(r["would_be_denied"])
        lines = [("" if name(re.search(r"syscall=(\d+)", l).group(1)) in mine else "# other app: ") + l
                 for t, l in recs if start <= t <= end]
        with open(out, "w") as fh:
            fh.write(f"# extracted afterwards (extract_audit_records.py): SECCOMP log records between {start:.0f} and "
                     f"{end:.0f} (epoch); records of other apps in log mode at the same time are marked '# other app'. "
                     f"This container's syscalls, by PID: would_be_denied in {os.path.basename(j)} = {json.dumps(r['would_be_denied'])}\n")
            fh.write("".join(l + "\n" for l in lines))
        print(f"{out}: {sum(not l.startswith('#') for l in lines)} this app, {sum(l.startswith('#') for l in lines)} other")
