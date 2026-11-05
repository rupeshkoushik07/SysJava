# coding=utf-8
#
# Generic swat4j JNI mapper
# Usage:
#   python3 swat4j_mapping.py --libs-dir LIBS_<image>/ --methods outputs_<image>/native_methods.txt
#
# Optional flags:
#   --output-dir DIR        Where to write results (default: same dir as methods file)
#   --jdk-lib PATH          JDK native lib directory (default: /usr/lib/jvm/java-8-openjdk-amd64/jre/lib/amd64)
#   --openjdk-src PATH      OpenJDK native source tree (default: .tmp_jdk8_native/jdk/src/share/native)
#

import subprocess
import os
import sys
import time
import re
import glob
import argparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Global set to track every .so file scanned during the run
scanned_libs = set()


def println():
    print("-" * 120)


# ─── Auto-discover app .so files by pattern ────────────────────────────────────

def find_so_files(libs_dir, pattern):
    """Return list of .so paths in libs_dir whose basename contains `pattern`."""
    hits = []
    if not os.path.isdir(libs_dir):
        return hits
    for f in sorted(os.listdir(libs_dir)):
        if pattern in f and '.so' in f:
            hits.append(os.path.join(libs_dir, f))
    return hits


# ─── Build maps ────────────────────────────────────────────────────────────────

def build_netty_map(libs_dir):
    """Scan LIBS_DIR for any netty .so files and extract netty_* symbols."""
    res = {}
    so_files = find_so_files(libs_dir, 'netty')
    if not so_files:
        print("  No netty .so files found in %s, skipping" % libs_dir)
        return res
    for so_path in so_files:
        scanned_libs.add(so_path)
        command = "objdump -dj .text %s 2>/dev/null | grep 'netty_.*>:' | awk '{print $2}'" % so_path
        lines = os.popen(command).readlines()
        for line in lines:
            line = line.strip('\n')[1:-2]  # strip < and >:
            native_method = line.replace('_', '.')
            if native_method not in res:
                res[native_method] = line + ' ' + so_path
    print("  Found %d netty symbols from %d .so files" % (len(res), len(so_files)))
    return res


def build_jffi_map(libs_dir):
    """Scan LIBS_DIR for JFFI .so files and extract Java_com_kenai_jffi_* symbols."""
    res = {}
    so_files = find_so_files(libs_dir, 'jffi')
    if not so_files:
        print("  No jffi .so files found in %s, skipping" % libs_dir)
        return res
    for so_path in so_files:
        scanned_libs.add(so_path)
        command = "objdump -dj .text %s 2>/dev/null | grep 'Java_com.*>:' | awk '{print $2}'" % so_path
        lines = os.popen(command).readlines()
        for line in lines:
            line = line.strip('\n')[1:-2]
            dot_name = line[5:].replace('_', '.')
            if dot_name not in res:
                res[dot_name] = line + ' ' + so_path
    print("  Found %d jffi symbols from %d .so files" % (len(res), len(so_files)))
    return res


def build_tc_map(libs_dir):
    """Scan LIBS_DIR for tcnative .so files and extract Java_org* symbols."""
    res = {}
    so_files = find_so_files(libs_dir, 'tcnative')
    if not so_files:
        print("  No tcnative .so files found in %s, skipping" % libs_dir)
        return res
    for so_path in so_files:
        scanned_libs.add(so_path)
        command = "objdump -dj .text %s 2>/dev/null | grep 'Java_org.*>:' | awk '{print $2}'" % so_path
        lines = os.popen(command).readlines()
        for line in lines:
            line = line.strip('\n')[1:-2]
            dot_name = line[5:].replace('_', '.')
            if dot_name not in res:
                res[dot_name] = line + ' ' + so_path
    print("  Found %d tcnative symbols from %d .so files" % (len(res), len(so_files)))
    return res


def build_org_map(libs_dir):
    """Scan LIBS_DIR for sigar .so files and extract Java_org* symbols."""
    res = {}
    so_files = find_so_files(libs_dir, 'sigar')
    if not so_files:
        print("  No sigar .so files found in %s, skipping" % libs_dir)
        return res
    for so_path in so_files:
        scanned_libs.add(so_path)
        command = "objdump -dj .text %s 2>/dev/null | grep 'Java_org.*>:' | awk '{print $2}'" % so_path
        lines = os.popen(command).readlines()
        for line in lines:
            line = line.strip('\n')[1:-2]
            dot_name = line[5:].replace('_', '.')
            if dot_name not in res:
                res[dot_name] = line + ' ' + so_path
    print("  Found %d sigar symbols from %d .so files" % (len(res), len(so_files)))
    return res


def build_JVM_map(openjdk_src, jdk_libjvm_path):
    """Build JVM_XXX map from OpenJDK native source .c files."""
    jvm_dict = {}
    if not os.path.isdir(openjdk_src):
        print("  Warning: OpenJDK native source not found at %s, skipping JVM_ mapping" % openjdk_src)
        return jvm_dict
    for home, dirs, files in os.walk(openjdk_src):
        for file in files:
            if file[-2:] == '.c':
                path = home + '/' + file
                pkg = home[len(openjdk_src) + 1:] + '/' + file[:-2] + '/'
                pkg = pkg.replace('/', '.')
                text = str(os.popen('cat ' + path + ' | grep \'&JVM_\'').readlines())
                idx = 0
                while idx < len(text):
                    if text[idx] == '{':
                        idx += 1
                        tmp = idx
                        while idx < len(text) and text[idx] != '}':
                            idx += 1
                            item = text[tmp:idx]
                        parts = item.split(',')
                        native = parts[0].strip('\"')
                        jni = parts[-1]
                        tmp = -1
                        while jni[tmp] != '&':
                            tmp -= 1
                        jni = jni[tmp + 1:]
                        jvm_dict[pkg + native] = jni + ' ' + jdk_libjvm_path
                    idx += 1
    print("  Found %d JVM_XXX entries" % len(jvm_dict))
    return jvm_dict


def scan_so_files_recursive(directory):
    """Walk directory recursively and return all .so file paths."""
    so_files = []
    if not os.path.isdir(directory):
        return so_files
    for root, dirs, files in os.walk(directory):
        for f in sorted(files):
            if '.so' in f:
                so_files.append(os.path.join(root, f))
    return so_files


def read_java_symbols_from_so(native_map, so_path):
    """Scan a .so file with nm -D for Java_* exported symbols."""
    scanned_libs.add(so_path)
    added = 0
    try:
        result = subprocess.run(
            ["nm", "-D", so_path],
            capture_output=True, text=True, timeout=30
        )
        for line in result.stdout.splitlines():
            parts = line.strip().split()
            if len(parts) == 3 and parts[1] == 'T' and parts[2].startswith('Java_'):
                sym = parts[2]
                if '@@' in sym:
                    sym = sym.split('@@')[0]
                jni_name = sym[5:]  # strip "Java_"
                dot_name = jni_name.replace('_', '.')
                if dot_name not in native_map:
                    native_map[dot_name] = jni_name + ' ' + so_path
                    added += 1
    except Exception:
        pass
    return native_map, added


def build_java_map(jdk_lib_path, libs_dir):
    """Build Java_XXX map from JDK .so files + app LIBS_DIR .so files."""
    native_map = {}

    # 1. Scan JDK .so files
    jdk_count = 0
    jdk_scanned = []
    if os.path.isdir(jdk_lib_path):
        for f in sorted(os.listdir(jdk_lib_path)):
            so_path = os.path.join(jdk_lib_path, f)
            if not os.path.isfile(so_path) or not f.endswith('.so'):
                continue
            native_map, added = read_java_symbols_from_so(native_map, so_path)
            jdk_count += added
            jdk_scanned.append(f)
        # Also scan server/ subdirectory for libjvm.so
        server_dir = os.path.join(jdk_lib_path, "server")
        if os.path.isdir(server_dir):
            for f in sorted(os.listdir(server_dir)):
                so_path = os.path.join(server_dir, f)
                if os.path.isfile(so_path) and '.so' in f:
                    native_map, added = read_java_symbols_from_so(native_map, so_path)
                    jdk_count += added
                    jdk_scanned.append("server/" + f)
    else:
        print("  Warning: JDK lib path not found at %s" % jdk_lib_path)

    # 2. Scan app LIBS_DIR for Java_* symbols (top-level .so files only)
    app_count = 0
    app_scanned = []
    if os.path.isdir(libs_dir):
        for f in sorted(os.listdir(libs_dir)):
            so_path = os.path.join(libs_dir, f)
            if not os.path.isfile(so_path) or '.so' not in f:
                continue
            native_map, added = read_java_symbols_from_so(native_map, so_path)
            app_count += added
            app_scanned.append(f)

    print("  JDK .so scanned:  %d files from %s" % (len(jdk_scanned), jdk_lib_path))
    print("  JDK .so symbols:  %d" % jdk_count)
    print("  App .so scanned:  %d files from %s" % (len(app_scanned), libs_dir))
    print("  App .so symbols:  %d" % app_count)
    print("  Total (deduped):  %d" % len(native_map))

    return native_map


# ─── Aggregate mapping ─────────────────────────────────────────────────────────

def aggregate(named_maps, combined_map, native_methods):
    """
    Map native methods to JNI functions using named strategies in priority order.
    Falls back to netty heuristic for io.netty.* methods.
    """
    cnt = 0
    res = {}
    mapped_methods = []    # (method, jni_name, libpath, strategy)
    unmapped_methods = []

    for m in native_methods:
        found = False
        # Try each named map in priority order
        for strategy_name, smap in named_maps:
            if m in smap:
                val = smap[m].split(' ')
                jni_name = val[0]
                libpath = val[1]
                if cnt < 1:
                    println()
                    print("Example: %s -> %s (%s) [%s]" % (m, jni_name, libpath, strategy_name))
                    println()
                    cnt += 1
                if libpath not in res:
                    res[libpath] = []
                if jni_name.startswith("JVM") or jni_name.startswith("sun") or "org" in jni_name:
                    res[libpath].append(jni_name)
                else:
                    res[libpath].append("Java_" + jni_name)
                mapped_methods.append((m, jni_name, libpath, strategy_name))
                found = True
                break
        if found:
            continue
        # Netty heuristic: fuzzy match on method name suffix
        if m.startswith("io.netty"):
            end = m.split(".")[-1]
            for name in combined_map:
                if name.startswith("netty") and name.endswith(end):
                    val = combined_map[name].split(' ')
                    jni_name = val[0]
                    libpath = val[1]
                    if libpath not in res:
                        res[libpath] = []
                    res[libpath].append(jni_name)
                    mapped_methods.append((m, jni_name, libpath, "NETTY_HEURISTIC"))
                    found = True
                    break
        if not found:
            unmapped_methods.append(m)
    return res, mapped_methods, unmapped_methods


# ─── Intrinsic whitelist ──────────────────────────────────────────────────────

def load_intrinsic_whitelist(explicit_path=None, output_dir=None) -> set:
    """
    Load the JVM intrinsic whitelist — methods inlined by the JIT compiler
    that have no corresponding symbol in any .so file.
    Uses the same search logic as mapped_updated.py:
      1. Explicit path (--intrinsic-whitelist or INTRINSICS_FILE env)
      2. OUTPUTS_DIR/intrinsic_whitelist_all_jdks.txt
      3. cwd/intrinsic_whitelist_all_jdks.txt
      4. script_dir/intrinsic_whitelist_all_jdks.txt
      5. script_dir/outputs_*/intrinsic_whitelist_all_jdks.txt
    """
    candidates = []
    if explicit_path:
        candidates.append(explicit_path)
    env_path = os.environ.get("INTRINSICS_FILE")
    if env_path:
        candidates.append(env_path)
    if output_dir and output_dir not in (".", ""):
        candidates.append(os.path.join(output_dir, "intrinsic_whitelist_all_jdks.txt"))
    candidates.append("intrinsic_whitelist_all_jdks.txt")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(script_dir, "intrinsic_whitelist_all_jdks.txt"))
    candidates.extend(
        glob.glob(os.path.join(script_dir, "outputs_*", "intrinsic_whitelist_all_jdks.txt"))
    )

    seen = set()
    ordered = []
    for path in candidates:
        if path and path not in seen:
            ordered.append(path)
            seen.add(path)

    for path in ordered:
        if os.path.isfile(path):
            entries = set()
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        entries.add(line)
            print(f"INFO: Loaded {len(entries)} intrinsic methods from {path}")
            return entries

    print("INFO: No intrinsic whitelist found (optional). Skipping intrinsic classification.")
    return set()


# ─── Main ──────────────────────────────────────────────────────────────────────

def discover_jdk_libs_subdirs(libs_dir):
    """Auto-discover JDK<N>_LIBS/ subdirectories inside libs_dir."""
    jdk_dirs = []
    if not os.path.isdir(libs_dir):
        return jdk_dirs
    for entry in sorted(os.listdir(libs_dir)):
        if re.match(r'^JDK\d+_LIBS$', entry):
            full = os.path.join(libs_dir, entry)
            if os.path.isdir(full):
                jdk_dirs.append(full)
    return jdk_dirs


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="swat4j JNI mapper - map Java native methods to JNI function symbols in .so files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  # Explicit args:
  python3 swat4j_mapping.py --libs-dir LIBS_zookeeper_3.4.14 --methods outputs_zookeeper_3.4.14/native_methods.txt

  # Using env vars (same as mapped_updated.py):
  LIB_DIRS=LIBS_zookeeper_3.4.14 OUTPUTS_DIR=outputs_zookeeper_3.4.14 python3 swat4j_mapping.py
"""
    )
    parser.add_argument('--libs-dir', default=None,
                        help='Directory containing extracted .so libraries (default: LIB_DIRS env)')
    parser.add_argument('--methods', default=None,
                        help='Path to native_methods.txt (default: OUTPUTS_DIR/native_methods.txt)')
    parser.add_argument('--output-dir', default=None,
                        help='Directory for output files (default: OUTPUTS_DIR or same dir as --methods)')
    parser.add_argument('--jdk-lib', default='/usr/lib/jvm/java-8-openjdk-amd64/jre/lib/amd64',
                        help='JDK native library directory (default: JDK 8 amd64)')
    parser.add_argument('--openjdk-src', default=os.path.join(BASE_DIR, '.tmp_jdk8_native/jdk/src/share/native'),
                        help='OpenJDK native source tree for JVM_XXX mapping')
    parser.add_argument('--intrinsic-whitelist', default=None,
                        help='Path to intrinsic whitelist file (default: auto-discover from OUTPUTS_DIR, cwd, or script dir)')
    parser.add_argument('--extra-libs', nargs='*', default=[],
                        help='Additional library directories to scan (e.g. netty_libs netty_libs_all hawtjni_libs)')

    args = parser.parse_args()

    # Resolve libs_dir: CLI arg > LIB_DIRS env
    if args.libs_dir:
        libs_dir = os.path.abspath(args.libs_dir)
    else:
        env_lib = os.environ.get("LIB_DIRS") or os.environ.get("LIBS_IMAGE") or os.environ.get("LIBS_DIR")
        if env_lib:
            libs_dir = os.path.abspath(env_lib.split(os.pathsep)[0])
        else:
            print("ERROR: --libs-dir not given and LIB_DIRS env not set")
            sys.exit(1)

    # Resolve methods file: CLI arg > OUTPUTS_DIR/native_methods.txt
    env_outputs = os.environ.get("OUTPUTS_DIR", "").strip()
    if args.methods:
        methods_file = os.path.abspath(args.methods)
    elif env_outputs:
        methods_file = os.path.abspath(os.path.join(env_outputs, "native_methods.txt"))
    else:
        print("ERROR: --methods not given and OUTPUTS_DIR env not set")
        sys.exit(1)

    jdk_lib_path = os.path.abspath(args.jdk_lib)
    openjdk_src = os.path.abspath(args.openjdk_src)
    jdk_libjvm_path = os.path.join(jdk_lib_path, "server/libjvm.so")
    intrinsic_explicit = os.path.abspath(args.intrinsic_whitelist) if args.intrinsic_whitelist else None
    extra_libs_dirs = [os.path.abspath(d) for d in args.extra_libs if os.path.isdir(d)]

    # Auto-discover JDK<N>_LIBS/ subdirectories inside libs_dir
    jdk_sub_dirs = discover_jdk_libs_subdirs(libs_dir)
    if jdk_sub_dirs:
        print("Auto-discovered JDK lib subdirs:")
        for d in jdk_sub_dirs:
            print("  %s" % d)

    # Build combined list: primary libs_dir + JDK subdirs + extra dirs
    all_libs_dirs = [libs_dir] + jdk_sub_dirs + extra_libs_dirs

    if args.output_dir:
        out_dir = os.path.abspath(args.output_dir)
    elif env_outputs:
        out_dir = os.path.abspath(env_outputs)
    else:
        out_dir = os.path.dirname(methods_file)
    os.makedirs(out_dir, exist_ok=True)

    # Validate inputs
    if not os.path.isdir(libs_dir):
        print("ERROR: Libraries directory not found: %s" % libs_dir)
        sys.exit(1)
    if not os.path.isfile(methods_file):
        print("ERROR: Native methods file not found: %s" % methods_file)
        sys.exit(1)

    T1 = time.time()

    image_name = os.path.basename(libs_dir)
    if image_name.startswith("LIBS_"):
        image_name = image_name[5:]

    print("=" * 80)
    print("swat4j JNI Mapping: %s" % image_name)
    print("=" * 80)
    print("Native methods file: %s" % methods_file)
    print("Libraries directory: %s" % libs_dir)
    print("JDK lib path:        %s" % jdk_lib_path)
    print("OpenJDK source:      %s" % openjdk_src)
    print("Output directory:    %s" % out_dir)
    if jdk_sub_dirs:
        print("JDK lib subdirs:     %s" % ', '.join(os.path.basename(d) for d in jdk_sub_dirs))
    if extra_libs_dirs:
        print("Extra lib dirs:      %s" % ', '.join(os.path.basename(d) for d in extra_libs_dirs))
    print()

    # 1. Java_XXX from JDK + all lib dirs
    print("[1/6] Building Java_XXX map (JDK + app .so files)...")
    native_map = build_java_map(jdk_lib_path, libs_dir)
    # Also scan JDK<N>_LIBS subdirs and extra dirs for Java_* symbols (recursive)
    for extra_dir in jdk_sub_dirs + extra_libs_dirs:
        extra_added = 0
        so_files = scan_so_files_recursive(extra_dir)
        if so_files:
            print("  Scanning %s (%d .so files):" % (os.path.basename(extra_dir), len(so_files)))
            for so_path in so_files:
                rel = os.path.relpath(so_path, extra_dir)
                native_map, added = read_java_symbols_from_so(native_map, so_path)
                if added:
                    print("    %s: %d Java_* symbols" % (rel, added))
                extra_added += added
        if extra_added:
            print("  Extra .so symbols: %d (from %s)" % (extra_added, os.path.basename(extra_dir)))

    # 2. JVM_XXX from OpenJDK source
    print("[2/6] Building JVM_XXX map (OpenJDK source)...")
    native_JVM_map = build_JVM_map(openjdk_src, jdk_libjvm_path)

    # 3. JFFI - scan all lib dirs
    print("[3/6] Building JFFI map...")
    jffi_map = {}
    for d in all_libs_dirs:
        m = build_jffi_map(d)
        for k, v in m.items():
            if k not in jffi_map:
                jffi_map[k] = v

    # 4. Netty - scan all lib dirs
    print("[4/6] Building Netty map...")
    native_netty_map = {}
    for d in all_libs_dirs:
        m = build_netty_map(d)
        for k, v in m.items():
            if k not in native_netty_map:
                native_netty_map[k] = v

    # 5. tcnative - scan all lib dirs
    print("[5/6] Building tcnative map...")
    tc_map = {}
    for d in all_libs_dirs:
        m = build_tc_map(d)
        for k, v in m.items():
            if k not in tc_map:
                tc_map[k] = v

    # 6. Sigar - scan all lib dirs
    print("[6/6] Building sigar map...")
    org_map = {}
    for d in all_libs_dirs:
        m = build_org_map(d)
        for k, v in m.items():
            if k not in org_map:
                org_map[k] = v

    # Build named maps list (priority order) for strategy tracking
    named_maps = [
        ("Java_XXX",  native_map),
        ("JVM_XXX",   native_JVM_map),
        ("JFFI",      jffi_map),
        ("NETTY",     native_netty_map),
        ("TCNATIVE",  tc_map),
        ("SIGAR",     org_map),
    ]

    # Merged map for netty heuristic fallback
    combined_map = {}
    combined_map.update(native_map)
    combined_map.update(native_JVM_map)
    combined_map.update(jffi_map)
    combined_map.update(native_netty_map)
    combined_map.update(tc_map)
    combined_map.update(org_map)

    total_entries = len(combined_map)
    print("\nTotal entries in combined map: %d" % total_entries)

    # Read native methods
    native_methods = []
    with open(methods_file, 'r') as f:
        for line in f:
            m = line.strip()
            if m:
                native_methods.append(m)

    print("Total native methods to map: %d\n" % len(native_methods))

    # Run mapping
    jni_methods, mapped_methods, unmapped_methods = aggregate(named_maps, combined_map, native_methods)

    # ── Apply intrinsic classification to unmapped methods ──
    # Same logic and list as mapped_updated.py: mapping happens first,
    # then intrinsic is applied to the remaining unmapped methods.
    intrinsic_set = load_intrinsic_whitelist(
        explicit_path=intrinsic_explicit,
        output_dir=out_dir,
    )
    intrinsic_unmapped = sorted(set(unmapped_methods) & intrinsic_set)
    truly_unmapped_list = sorted(set(unmapped_methods) - intrinsic_set)
    truly_unmapped = len(truly_unmapped_list)

    # ── Strategy breakdown ──
    strategy_counts = {}
    for _, _, _, strategy in mapped_methods:
        strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1

    # ── Summary ──
    total = len(native_methods)
    mapped_count = len(mapped_methods)
    unmapped_count = len(unmapped_methods)

    print("\n" + "=" * 80)
    print("SUMMARY: %s" % image_name)
    print("=" * 80)
    print("Total native methods:  %d" % total)
    print("-" * 40)
    print("MAPPED:                %d  (%.1f%%)" % (mapped_count, 100.0 * mapped_count / total))
    for strategy, count in sorted(strategy_counts.items(), key=lambda x: -x[1]):
        print("  %-20s %d" % (strategy, count))
    print()
    print("UNMAPPED:              %d  (%.1f%%)" % (unmapped_count, 100.0 * unmapped_count / total))
    print("  %-20s %d" % ("Intrinsic", len(intrinsic_unmapped)))
    print("  %-20s %d" % ("Truly unmapped", truly_unmapped))
    print("=" * 80)

    # Aggregate: library -> JNI functions
    print("\nAGGREGATE: Library -> JNI functions")
    print("-" * 80)
    for libpath in sorted(jni_methods.keys()):
        funcs = jni_methods[libpath]
        print("\n%s (%d functions)" % (libpath, len(funcs)))
        for func in sorted(set(funcs)):
            print("  %s" % func)

    # ── Write output files ──
    mapped_file = os.path.join(out_dir, "swat4j_mapped_methods.txt")
    with open(mapped_file, 'w') as f:
        for m, jni_name, libpath, strategy in sorted(mapped_methods):
            f.write("%s -> %s @ %s [%s]\n" % (m, jni_name, libpath, strategy))
    print("\n\nMapped methods written to: %s" % mapped_file)

    unmapped_file = os.path.join(out_dir, "swat4j_unmapped_methods.txt")
    with open(unmapped_file, 'w') as f:
        for m in truly_unmapped_list:
            f.write("%s\n" % m)
    print("Unmapped methods written to: %s (%d)" % (unmapped_file, len(truly_unmapped_list)))

    intrinsic_file_out = os.path.join(out_dir, "swat4j_intrinsic_methods.txt")
    with open(intrinsic_file_out, 'w') as f:
        for m in intrinsic_unmapped:
            f.write("%s\n" % m)
    print("Intrinsic methods written to: %s (%d)" % (intrinsic_file_out, len(intrinsic_unmapped)))

    aggregate_file = os.path.join(out_dir, "swat4j_aggregate.txt")
    with open(aggregate_file, 'w') as f:
        for libpath in sorted(jni_methods.keys()):
            funcs = jni_methods[libpath]
            f.write("%s\n" % libpath)
            for func in sorted(set(funcs)):
                f.write("  %s\n" % func)
            f.write("\n")
    print("Aggregate mapping written to: %s" % aggregate_file)

    # Write summary file
    summary_file = os.path.join(out_dir, "swat4j_summary.txt")
    with open(summary_file, 'w') as f:
        f.write("SUMMARY: %s\n" % image_name)
        f.write("=" * 40 + "\n")
        f.write("Total native methods:  %d\n" % total)
        f.write("-" * 40 + "\n")
        f.write("MAPPED:                %d  (%.1f%%)\n" % (mapped_count, 100.0 * mapped_count / total))
        for strategy, count in sorted(strategy_counts.items(), key=lambda x: -x[1]):
            f.write("  %-20s %d\n" % (strategy, count))
        f.write("\n")
        f.write("UNMAPPED:              %d  (%.1f%%)\n" % (unmapped_count, 100.0 * unmapped_count / total))
        f.write("  %-20s %d\n" % ("Intrinsic", len(intrinsic_unmapped)))
        f.write("  %-20s %d\n" % ("Truly unmapped", truly_unmapped))
    print("Summary written to: %s" % summary_file)

    # Write libraries scanned file
    libs_scanned_file = os.path.join(out_dir, "swat4j_libraries_scanned.txt")
    with open(libs_scanned_file, 'w') as f:
        f.write("Libraries scanned: %d\n" % len(scanned_libs))
        f.write("=" * 60 + "\n\n")
        for so_path in sorted(scanned_libs):
            f.write("%s\n" % so_path)
    print("Libraries scanned written to: %s" % libs_scanned_file)

    T2 = time.time()
    print("\nTime: %.2fs" % (T2 - T1))
