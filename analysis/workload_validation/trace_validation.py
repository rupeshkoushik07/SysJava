#!/usr/bin/env python3
"""Traced pass for the paper's policy-validation table (missing / performed / permitted syscalls, new binaries /
libraries). Each app runs its workload once more with Docker's default seccomp (like `base`) while sysdig records,
for every process of the container from start-up to the end of the workload:
  - each distinct syscall (`syscall.type`, enter or exit event: newer sysdig sends many syscalls as exit events
    only) and the process name that made it; the container filter is a display filter (-d), because a capture
    filter makes sysdig enable only the syscalls it thinks the filter needs, and the format starts with `*` so
    events without an fd are printed too;
  - each shared library opened (`open*` of a path containing .so, successful) and each program executed (execve).
sysdig is started on the container name before `docker run`, as the pipeline's start-up discovery (sysdig_unified.sh)
does; its output is de-duplicated on the fly (awk), so the files stay small.
Then, against the published profile (run_validation.profile_path) and the pipeline's start-up dataset:
  performed = distinct syscalls (sysdig syscall.type, libseccomp names) of the container's processes, except
              runc's setup stages before the filter is installed (runc:[0:PARENT], runc:[1:CHILD])
  missing   = performed - profile
  new       = libraries / executables seen here whose file name is not in Dataset/LIBS_<t> / BINARIES_<t>
Usage: trace_validation.py <app> [<app> ...]      (WLV_RESULTS default: results/trace)
Output: results_trace/<app>/trace_1.{json,container.log,sysdig.txt}, results_trace/<app>/table_row.json
"""
import json, os, re, signal, subprocess, sys, time

os.environ.setdefault("WLV_RESULTS", "results/trace")
# Storm: the published 179-syscall profile (run_validation's default is the earlier 172 one)
os.environ.setdefault("WLV_STORM_PROFILE", os.path.expanduser(
    "~/Tutorial/EchoTrace/Final_results_JDK8/_tables/storm_no_false_ffm_fixes/storm_2.4.0-jdk8-buster.json"))
import run_validation as rv

HERE = rv.HERE
RES = f"{HERE}/{os.environ['WLV_RESULTS']}"
# sysdig's syscall.type names that differ from libseccomp's (the profiles' names)
ALIAS = {"pread": "pread64", "pwrite": "pwrite64", "prlimit": "prlimit64"}
# runc's setup stages run in the container's cgroup before runc:[2:INIT] installs the seccomp filter, so the
# profile never applies to them (mounts, pivot_root, sethostname, ...); counted separately
PRE_SECCOMP = {"runc:[0:PARENT]", "runc:[1:CHILD]"}


def dataset_names(t):
    # WLV_DATASETS: a folder of <t>/Dataset (the artifact unpacks 2_swat4j_vs_sysjava/sysjava_results/<t>/dataset/ there)
    ds = f"{os.environ.get('WLV_DATASETS', rv.R)}/{t}/Dataset"
    libs, bins = set(), set()
    for root, _, files in os.walk(f"{ds}/LIBS_{t}"):
        libs.update(files)
    for root, _, files in os.walk(f"{ds}/BINARIES_{t}"):
        bins.update(files)
    return libs, bins


def trace(app, data):
    name = f"wlv-{app}-trace-1"
    os.makedirs(f"{RES}/{app}", exist_ok=True)
    out = f"{RES}/{app}/trace_1.sysdig.txt"
    filt = f"container.name={name} and syscall.type exists"   # both directions: newer sysdig has exit-only syscalls
    cmd = (f"sudo -n sysdig --modern-bpf -d \"{filt}\" -p '*%evt.dir|%syscall.type|%evt.type|%proc.name|%proc.exepath|%evt.failed|%fd.name' "
           f"2>{out}.err | awk -F'|' '{{k=$2 FS $4; if ($3 ~ /^(open|openat|openat2|execve)$/ && $1==\"<\") k=$0; "
           f"if (!seen[k]++) print}}' > {out}")
    p = subprocess.Popen(cmd, shell=True, start_new_session=True)
    time.sleep(6)                                     # modern-bpf needs time to attach (sysdig_unified.sh: 5 s)
    res = rv.one_run(app, "trace", 1, data)           # mode "trace" = no --security-opt = Docker's default seccomp
    time.sleep(2)
    # only the sysdig process itself (its command line starts with "sysdig"; sudo's and the shell's do not)
    pids = subprocess.run(["pgrep", "-f", f"^sysdig --modern-bpf -d container.name={name} "], capture_output=True,
                          text=True).stdout.split()
    if pids:
        subprocess.run(["sudo", "-n", "kill", "-INT", *pids])
    try:
        p.wait(timeout=60)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGTERM)
    return res, out


def analyse(app, res, out):
    t = rv.APPS[app]["t"]
    prof = set()
    for blk in json.load(open(rv.profile_path(app)))["syscalls"]:
        prof.update(blk["names"])
    calls, by_proc, libs, exes = set(), {}, set(), set()
    other = set()
    for l in open(out, errors="replace"):
        f = l.rstrip("\n").split("|")
        if len(f) < 7:
            continue
        d, sc, ty, pn, exe, failed, fd = f[:7]
        s = ALIAS.get(sc, sc)
        if pn in PRE_SECCOMP:
            other.add(s)
        elif s:
            calls.add(s); by_proc.setdefault(s, set()).add(pn)
        if d == "<" and failed == "false":
            if ty.startswith("open") and re.search(r"\.so(\.[0-9]+)*$", fd):
                libs.add(fd)
            elif ty == "execve":
                exes.add(exe)
    dl, db = dataset_names(t)
    norm = lambda n: re.sub(r"[0-9]{6,}", "#", os.path.basename(n))   # JNI libraries extracted under random names
    dl, db = {norm(x) for x in dl}, {norm(x) for x in db}
    # extracted JNI copies under random names: the library each one is (its JAR ships it under that name)
    extracted = {r"/tmp/libnetty-transport-native-epoll[0-9]+\.so$": "libnetty-transport-native-epoll.so",
                 r"/tmp/jffi[0-9]+\.so$": "libjffi-1.2.so"}

    def known(x):
        b = os.path.basename(x)
        if norm(x) in dl or any(n.startswith(b + ".") for n in dl):   # unversioned symlink (libjemalloc.so -> .so.2)
            return b if norm(x) in dl else next(n for n in dl if n.startswith(b + "."))
        for pat, lib in extracted.items():
            if re.search(pat, x) and lib in dl:
                return lib
        return None
    renamed = {x: known(x) for x in sorted(libs) if known(x) and known(x) != os.path.basename(x)}
    new_libs = sorted(x for x in libs if not known(x))
    new_bins = sorted(x for x in exes if norm(x) not in db and norm(x) not in dl)
    missing = sorted(calls - prof)
    row = dict(app=app, image=rv.APPS[app]["image"], ops_ok=res["ops_ok"], ops_failed=res["ops_failed"],
               performed=len(calls), permitted=len(prof), missing=missing,
               missing_by_process={s: sorted(by_proc[s]) for s in missing},
               libraries_loaded=len(libs), new_libraries=new_libs, loaded_under_other_name=renamed, executables=sorted(exes), new_binaries=new_bins,
               runc_setup_syscalls=sorted(other), performed_syscalls=sorted(calls))
    json.dump(row, open(f"{RES}/{app}/table_row.json", "w"), indent=1)
    print(f"{app}: ops ok={res['ops_ok']} failed={res['ops_failed']}  missing/performed/permitted = "
          f"{len(missing)}/{len(calls)}/{len(prof)} {missing}  new bins/libs = {len(new_bins)}/{len(new_libs)}", flush=True)
    return row


def main():
    if sys.argv[1] == "--analyse":                   # re-analyse saved traces
        for app in sys.argv[2:]:
            analyse(app, json.load(open(f"{RES}/{app}/trace_1.json")), f"{RES}/{app}/trace_1.sysdig.txt")
        return
    data = rv.prepare()
    for app in sys.argv[1:]:
        res, out = trace(app, data)
        analyse(app, res, out)


if __name__ == "__main__":
    main()
