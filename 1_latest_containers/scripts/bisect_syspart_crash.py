#!/usr/bin/env python3
"""Exclude only the start functions that crash SysPart, and analyse the rest.

Rule (user decision 2026-11-05): when SysPart's call-graph step (-a 23)
segfaults on a library, bisect its start list to find the start functions
that crash it, rerun the library through the normal compute_syscalls.sh
wrapper with the remaining starts, and record the excluded starts in
excluded_starts_syspart_crash.txt next to the result ("unanalysable
(SysPart crash)"). SysPart itself is not modified.

Usage: bisect_syspart_crash.py <result-dir> <library-file> <start-file> <libs-dir>
  result-dir   existing (crashed) result directory, e.g.
               workspaces/<t>/syscalls_unanalysed_<t>/libgcrypt.so.20
  library-file the analysed library (Dataset_symbolized/LIBS_<t>/...)
  start-file   the start-function file the pipeline used
  libs-dir     LIBS_<t> root, for USER_LIBRARY_PATH (same rule as the pipeline)
The crashed result is kept as <result-dir>.syspart_crash.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
APP_DIR = REPO / "SysPartCode" / "analysis" / "app"
TIMEOUT_S = 3600


def user_library_path(libs_dir: Path) -> str:
    paths = [str(libs_dir)]
    for jdk_dir in sorted(libs_dir.glob("JDK*_LIBS")):
        if jdk_dir.is_dir():
            paths.append(str(jdk_dir))
            paths += [str(p) for p in sorted(jdk_dir.rglob("*")) if p.is_dir()]
    return ":".join(paths)


def resolve(starts: list[str], allfunctions: Path) -> dict[str, str]:
    """Map each start name to its spelling in SysPart's function list
    (name@@VERSION for versioned exports), as compute_syscalls_lowmem.sh does."""
    have, versioned = set(), {}
    for line in allfunctions.read_text(errors="replace").splitlines():
        if not line.split():
            continue
        name = line.split()[0]
        have.add(name)
        if "@" in name:
            versioned.setdefault(name.split("@", 1)[0], name)
    return {s: s if s in have or s not in versioned else versioned[s] for s in starts}


class Probe:
    def __init__(self, library: Path, env: dict):
        self.library, self.env, self.runs = library, env, 0

    def crashes(self, names: list[str]) -> int:
        """Exit status of the call-graph step for these (resolved) starts; 0 = ok."""
        self.runs += 1
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as handle:
            handle.write("\n".join(names) + "\n")
            path = handle.name
        try:
            proc = subprocess.run(
                ["bash", "-c", f'ulimit -s 1048576; exec ./syspart -p "$0" -s "$1" -i -a 23 > /dev/null 2>&1',
                 str(self.library), path],
                cwd=APP_DIR, env=self.env, timeout=TIMEOUT_S)
            return proc.returncode
        except subprocess.TimeoutExpired:
            return 124
        finally:
            os.unlink(path)


def bisect(probe: Probe, names: list[str], rc: int, found: dict[str, int]) -> None:
    """names crash with status rc; record the minimal crashing starts in found."""
    if len(names) == 1:
        found[names[0]] = rc
        print(f"  crashing start: {names[0]} (exit {rc})", flush=True)
        return
    half = len(names) // 2
    left, right = names[:half], names[half:]
    rc_left, rc_right = probe.crashes(left), probe.crashes(right)
    if rc_left:
        bisect(probe, left, rc_left, found)
    if rc_right:
        bisect(probe, right, rc_right, found)
    if not rc_left and not rc_right:
        # Only the combination crashes: exclude the smaller half that, with the
        # other half, still crashes (found by retrying with one half removed).
        for part in (left, right):
            rest = [n for n in names if n not in part]
            if probe.crashes(rest) == 0:
                for n in part:
                    found[n] = rc
                print(f"  crash needs a combination; excluding {len(part)} starts", flush=True)
                return
        for n in names:
            found[n] = rc


def main(argv: list[str]) -> int:
    result_dir, library, start_file, libs_dir = (Path(a).resolve() for a in argv[:4])
    starts = [l.strip() for l in start_file.read_text(errors="replace").splitlines() if l.strip()]
    allfunctions = result_dir / "allfunctions.txt"
    spelling = resolve(starts, allfunctions)
    env = dict(os.environ, USER_LIBRARY_PATH=user_library_path(libs_dir))
    probe = Probe(library, env)

    resolved = [spelling[s] for s in starts]
    rc = probe.crashes(resolved)
    print(f"{library.name}: {len(starts)} starts, full list exit {rc}", flush=True)
    found: dict[str, int] = {}
    if rc:
        bisect(probe, resolved, rc, found)
    print(f"{library.name}: {len(found)} crashing starts after {probe.runs} SysPart runs", flush=True)

    excluded_resolved = set(found)
    kept = [s for s in starts if spelling[s] not in excluded_resolved]
    crashed_copy = result_dir.with_name(result_dir.name + ".syspart_crash")
    if crashed_copy.exists():
        shutil.rmtree(crashed_copy)
    shutil.move(str(result_dir), str(crashed_copy))
    result_dir.mkdir()
    kept_file = result_dir / "startfuncs_kept.txt"
    kept_file.write_text("\n".join(kept) + "\n")
    with (result_dir / "logfile.txt").open("ab") as log:
        proc = subprocess.run(["src/scripts/compute_syscalls.sh", str(library), str(result_dir),
                               str(kept_file), "--log"], cwd=APP_DIR, env=env,
                              stdout=log, stderr=subprocess.STDOUT)
    syscalls = result_dir / "syscalls.txt"
    count = len(syscalls.read_text().split()) if syscalls.is_file() else 0
    with (result_dir / "excluded_starts_syspart_crash.txt").open("w") as handle:
        handle.write("# unanalysable (SysPart crash): start functions excluded because SysPart's\n"
                     "# call-graph step (-a 23) exits non-zero with them; the remaining starts\n"
                     f"# were analysed normally. library={library}\n# start\tresolved_name\texit_code\n")
        for s in starts:
            if spelling[s] in excluded_resolved:
                handle.write(f"{s}\t{spelling[s]}\t{found[spelling[s]]}\n")
    (crashed_copy / "SYSPART_CRASHED.txt").unlink(missing_ok=True)
    print(f"{library.name}: rerun with {len(kept)}/{len(starts)} starts exit {proc.returncode}, "
          f"{count} syscalls; excluded {len(found)}", flush=True)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
