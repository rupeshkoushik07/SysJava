#!/usr/bin/env python3
"""Recover native libraries that the application unpacks from its JARs at run time.

netty, jffi and similar libraries copy a .so out of their JAR into /tmp under a
random name (e.g. /tmp/libnetty-transport-native-epoll2890788407668302447.so,
/tmp/jffi1099729192176773221.so), load it and delete it. The capture sees the
load, but the extraction step copies libraries from the container's file system
only, so these never reach LIBS_<image>/ and nothing analyses them.

For every library the capture saw loaded whose file name is not in LIBS_, this
looks for a Linux x86-64 entry with the same base name in the dataset's JARs and
copies it into LIBS_ under its name in the JAR. Base names drop a leading "lib",
the ".so", a version suffix ("-1.2") and the random digits ("2890788407668302447").

    extract_jar_natives.py --loaded libs_loaded_raw.txt --jars JARFILES_<image> \
        --libs LIBS_<image> [--report jar_natives_recovered.tsv]
"""
import argparse
import hashlib
import re
import sys
import zipfile
from pathlib import Path

LINUX_X86_64 = re.compile(r'(linux|Linux).*(x86[-_]64|amd64)|(x86[-_]64|amd64).*(linux|Linux)')


def stem(name):
    s = name.rsplit('/', 1)[-1]
    s = re.sub(r'\.so(\.[0-9.]+)?$', '', s)
    s = re.sub(r'^lib', '', s)
    s = re.sub(r'[0-9]{6,}$', '', s)      # random suffix of the unpacked copy
    s = re.sub(r'-[0-9][0-9.]*$', '', s)  # version suffix
    return s


def jar_candidates(jars_dir):
    """stem -> {sha256: (jar, entry)} for Linux x86-64 (or arch-less) .so entries."""
    found = {}
    for jar in sorted(Path(jars_dir).rglob('*.jar')):
        try:
            with zipfile.ZipFile(jar) as z:
                for entry in z.namelist():
                    if not entry.endswith('.so'):
                        continue
                    parent = entry.rsplit('/', 1)[0] if '/' in entry else ''
                    if not (LINUX_X86_64.search(parent) or parent in ('META-INF/native', '')):
                        continue
                    digest = hashlib.sha256(z.read(entry)).hexdigest()
                    found.setdefault(stem(entry), {})[digest] = (jar, entry)
        except (zipfile.BadZipFile, OSError):
            continue
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--loaded', required=True)
    ap.add_argument('--jars', required=True)
    ap.add_argument('--libs', required=True)
    ap.add_argument('--report')
    args = ap.parse_args()

    libs = Path(args.libs)
    have = {p.name for p in libs.rglob('*') if p.is_file() or p.is_symlink()}
    loaded = set()
    for line in Path(args.loaded).read_text(errors='replace').splitlines():
        for field in line.split():
            if field.startswith('/') and re.search(r'\.so(\.[0-9.]+)?$', field):
                loaded.add(field)
    # A loaded name that is a symlink to a copied library (libjemalloc.so ->
    # libjemalloc.so.2) is present under its real name: compare up to ".so".
    def base(n):
        return n[:n.index('.so') + 3] if '.so' in n else n
    have_base = {base(n) for n in have}
    # Already extracted under its JAR name (jffi1099...so is libjffi-1.2.so).
    have_stem = {stem(n) for n in have}
    missing = sorted(p for p in loaded
                     if p.rsplit('/', 1)[-1] not in have and base(p.rsplit('/', 1)[-1]) not in have_base
                     and stem(p) not in have_stem)
    if not missing:
        print('jar natives: every loaded library is in LIBS_')
        return 0

    candidates = jar_candidates(args.jars)
    rows = []
    for path in missing:
        hits = candidates.get(stem(path), {})
        if len(hits) == 1:
            jar, entry = next(iter(hits.values()))
            dest = libs / entry.rsplit('/', 1)[-1]
            if not dest.exists():
                with zipfile.ZipFile(jar) as z:
                    dest.write_bytes(z.read(entry))
            rows.append((path, 'recovered', f'{jar.name}!{entry}', dest.name))
        elif hits:
            rows.append((path, 'ambiguous', ' '.join(f'{j.name}!{e}' for j, e in hits.values()), ''))
        else:
            rows.append((path, 'not_in_jars', '', ''))
    for row in rows:
        print('jar natives: %-70s %-11s %s %s' % row)
    if args.report:
        with open(args.report, 'w') as f:
            f.write('loaded_path\tstatus\tsource\tlibs_name\n')
            for row in rows:
                f.write('\t'.join(row) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
