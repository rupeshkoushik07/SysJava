#!/bin/sh
#
# Install distro debug packages inside a running container and emit a tar of
# /usr/lib/debug/.build-id to stdout.
#
# Invoked by download_container_debug_symbols.py after public debuginfod
# mirrors fail to resolve some Build IDs. Expected usage:
#
#   docker cp scripts/install_container_dbgsym.sh <ct>:/tmp/
#   docker cp <libs-list>                        <ct>:/tmp/target-libs.txt
#   docker exec -i <ct> sh /tmp/install_container_dbgsym.sh > out.tar
#
# /tmp/target-libs.txt holds one absolute library path per line. Each path is
# mapped to its owning package, and the matching dbgsym/debuginfo package is
# installed at the exact installed version. Mirrors are enabled on first use;
# containers that have no package manager (Alpine without -dbg packages,
# distroless, scratch) short-circuit with a one-line diagnostic on stderr.
#
# All failures are non-fatal: the script always tars whatever /usr/lib/debug
# contains at the end. The Python caller verifies each .debug matches its
# expected GNU Build ID and discards mismatches.
#
# The container's filesystem is modified (new apt sources, installed packages).
# Callers that want to undo it can `docker restart` or rebuild the container.

set -eu

LIBS_FILE=/tmp/target-libs.txt
DEBUG_ROOT=/usr/lib/debug

log() { printf '[install_container_dbgsym] %s\n' "$*" >&2; }

if [ ! -s "$LIBS_FILE" ]; then
    log "no target libraries supplied (empty $LIBS_FILE)"
    tar -cf - -T /dev/null
    exit 0
fi

ID=""
VERSION_CODENAME=""
if [ -r /etc/os-release ]; then
    # shellcheck disable=SC1091
    . /etc/os-release
fi

install_debian_family() {
    # Debian puts dbgsyms on debian-debug/<codename>-debug. Ubuntu uses
    # ddebs.ubuntu.com and needs its own signing key. Both set VERSION_CODENAME
    # in /etc/os-release — if that's empty we can't construct a valid URL and
    # bail rather than silently fetch nothing.
    if [ -z "$VERSION_CODENAME" ]; then
        log "no VERSION_CODENAME in /etc/os-release; cannot enable dbgsym mirror"
        return 1
    fi

    case "$ID" in
        debian)
            if [ ! -f /etc/apt/sources.list.d/debug.list ]; then
                echo "deb http://deb.debian.org/debian-debug/ ${VERSION_CODENAME}-debug main" \
                    > /etc/apt/sources.list.d/debug.list
                log "added debian-debug mirror for ${VERSION_CODENAME}"
            fi
            ;;
        ubuntu)
            if [ ! -f /etc/apt/sources.list.d/ddebs.list ]; then
                {
                    echo "deb http://ddebs.ubuntu.com ${VERSION_CODENAME} main restricted universe multiverse"
                    echo "deb http://ddebs.ubuntu.com ${VERSION_CODENAME}-updates main restricted universe multiverse"
                } > /etc/apt/sources.list.d/ddebs.list
                log "added ddebs mirror for ${VERSION_CODENAME}"
            fi
            apt-get update -qq 2>/dev/null || true
            apt-get install -y --no-install-recommends ubuntu-dbgsym-keyring 2>/dev/null || true
            ;;
        *)
            log "unknown apt-based ID: $ID"
            return 1
            ;;
    esac

    if ! apt-get update -qq; then
        log "apt-get update failed"
        return 1
    fi

    # Build a de-duplicated list of <pkg>=<installed-version> targets. Pinning
    # the version matters: debuginfod misses happen precisely when the pool
    # ages out a point release, so grabbing the "current" dbgsym would install
    # a mismatched Build ID that the Python caller then discards.
    targets=""
    while IFS= read -r raw; do
        [ -z "$raw" ] && continue
        lib="$(readlink -f "$raw" 2>/dev/null || printf '%s' "$raw")"
        pkg="$(dpkg-query -S "$lib" 2>/dev/null | head -n1 | cut -d: -f1 || true)"
        [ -z "$pkg" ] && continue
        ver="$(dpkg-query -W -f='${Version}' "$pkg" 2>/dev/null || true)"
        [ -z "$ver" ] && continue
        for suffix in -dbgsym -dbg; do
            cand="${pkg}${suffix}"
            if apt-cache show "${cand}=${ver}" >/dev/null 2>&1; then
                case " $targets " in
                    *" ${cand}=${ver} "*) ;;
                    *) targets="$targets ${cand}=${ver}" ;;
                esac
                break
            fi
        done
    done < "$LIBS_FILE"

    if [ -z "$targets" ]; then
        log "no matching dbgsym packages found for requested libraries"
        return 0
    fi
    log "installing: $targets"
    # --no-install-recommends keeps the blast radius smaller; dbgsym packages
    # recommend their main package which is already installed, so this is a
    # no-op in the happy case.
    # shellcheck disable=SC2086
    apt-get install -y --no-install-recommends $targets || log "apt-get install returned non-zero (continuing)"
}

install_rpm_family() {
    # dnf's debuginfo-install handles mirror enablement and version pinning on
    # its own, so this branch is much shorter than the apt one.
    pm=""
    if command -v dnf >/dev/null 2>&1; then pm=dnf
    elif command -v yum >/dev/null 2>&1; then pm=yum
    else
        log "no dnf/yum available on $ID"
        return 1
    fi

    pkgs=""
    while IFS= read -r raw; do
        [ -z "$raw" ] && continue
        lib="$(readlink -f "$raw" 2>/dev/null || printf '%s' "$raw")"
        pkg="$(rpm -qf --queryformat '%{NAME}\n' "$lib" 2>/dev/null | head -n1 || true)"
        [ -z "$pkg" ] && continue
        case " $pkgs " in
            *" $pkg "*) ;;
            *) pkgs="$pkgs $pkg" ;;
        esac
    done < "$LIBS_FILE"
    [ -z "$pkgs" ] && { log "no RPM owners found for requested libraries"; return 0; }

    log "installing debuginfo for: $pkgs"
    # shellcheck disable=SC2086
    "$pm" debuginfo-install -y $pkgs 2>/dev/null \
        || "$pm" install -y $(printf '%s-debuginfo ' $pkgs) 2>/dev/null \
        || log "$pm debuginfo install returned non-zero (continuing)"
}

install_alpine() {
    # Alpine ships -dbg subpackages for a minority of libs. This is best-effort
    # and routinely comes up empty.
    pkgs=""
    while IFS= read -r raw; do
        [ -z "$raw" ] && continue
        lib="$(readlink -f "$raw" 2>/dev/null || printf '%s' "$raw")"
        pkg="$(apk info --who-owns "$lib" 2>/dev/null | awk '{print $NF}' | sed 's/-[0-9].*$//' | head -n1 || true)"
        [ -z "$pkg" ] && continue
        case " $pkgs " in
            *" $pkg "*) ;;
            *) pkgs="$pkgs ${pkg}-dbg" ;;
        esac
    done < "$LIBS_FILE"
    [ -z "$pkgs" ] && { log "no apk owners found"; return 0; }

    log "attempting: $pkgs"
    # shellcheck disable=SC2086
    apk add --no-cache $pkgs 2>/dev/null || log "apk add returned non-zero (continuing)"
}

case "$ID" in
    debian|ubuntu) install_debian_family || log "apt install step failed; tarring whatever exists" ;;
    rhel|centos|fedora|rocky|almalinux|amzn|ol) install_rpm_family || log "rpm install step failed; tarring whatever exists" ;;
    alpine) install_alpine || log "apk install step failed; tarring whatever exists" ;;
    "") log "no /etc/os-release found; cannot install dbg packages (distroless/scratch?)" ;;
    *) log "unsupported distro ID '$ID'; skipping install" ;;
esac

# Always tar whatever landed. Even a partial result is useful: debuginfod may
# have resolved some IDs independently and dropped them here via side channels.
if [ -d "$DEBUG_ROOT/.build-id" ]; then
    tar -cf - -C "$DEBUG_ROOT" .build-id
else
    log "no $DEBUG_ROOT/.build-id after install step"
    tar -cf - -T /dev/null
fi
