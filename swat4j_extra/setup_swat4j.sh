#!/usr/bin/env bash
#
# One-time setup of the SWAT4J baseline (only needed for SWAT4J=1 in
# 2_swat4j_vs_sysjava/reproduce.sh). SWAT4J is used UNMODIFIED: upstream code at
# a fixed commit; only its environment (OpenJDK 8, the paths it hard-codes) is
# provided.
#
#   swat4j/setup_swat4j.sh
#
# Needs: OpenJDK 8 at /usr/lib/jvm/java-8-openjdk-amd64 (apt install openjdk-8-jdk),
# sudo (SWAT4J hard-codes /home/mrx/Desktop and /usr/local/apr/lib; each app runs
# in a private mount namespace with those paths bind-mounted), strace, bc.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SWAT4J_URL="${SWAT4J_URL:-https://github.com/facumolina/SWAT4J.git}"
SWAT4J_COMMIT="${SWAT4J_COMMIT:-6929d66}"
JAVAC8=/usr/lib/jvm/java-8-openjdk-amd64/bin/javac
[ -x "$JAVAC8" ] || { echo "install openjdk-8-jdk first"; exit 1; }

if [ ! -d "$HERE/run/.git" ]; then
    git clone "$SWAT4J_URL" "$HERE/run"
fi
git -C "$HERE/run" checkout -q "$SWAT4J_COMMIT"
# Only the bytecode_new tracer is compiled (other packages need javaparser and are unused).
if [ ! -d "$HERE/run/classes" ]; then
    (cd "$HERE/run" && mkdir -p classes \
        && "$JAVAC8" -nowarn -encoding UTF-8 -cp asm-8.0.jar -d classes src/main/java/com/sspku/jtracer/bytecode_new/*.java)
fi
# SWAT4J reads OpenJDK 8 native sources from /home/mrx/Desktop/native; the copy
# used for the paper ships in mrx_desktop/native (bind-mounted there per app).
[ -d "$HERE/mrx_desktop/native" ] || { echo "mrx_desktop/native missing from the artifact"; exit 1; }
echo "SWAT4J ready: $HERE/run @ $(git -C "$HERE/run" rev-parse --short HEAD)"
