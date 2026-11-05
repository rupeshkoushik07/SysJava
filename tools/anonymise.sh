#!/usr/bin/env bash
# Replace author-identifying strings in every text file of the artifact.
#   anonymise.sh <dir>          rewrite in place
#   anonymise.sh --check <dir>  list files that still contain one (exit 1 if any)
# The patterns are assembled from pieces so this file never matches itself.
set -euo pipefail
CHECK=0; [ "${1:-}" = "--check" ] && { CHECK=1; shift; }
DIR="${1:?dir}"
U="rup""esh"; P="pun""na"; K="kou""shik"; M="madri""sec"; S="shelf""merch"
PATTERN="$U|$P|$K|$M|$S"
list() { grep -rIliE "$PATTERN" "$DIR" --exclude-dir=.git --exclude=anonymise.sh || true; }
if [ "$CHECK" = 1 ]; then
    hits="$(list)"
    if [ -n "$hits" ]; then echo "identifying strings remain in:"; echo "$hits"; exit 1; fi
    echo "anonymity check: clean"; exit 0
fi
list | while IFS= read -r f; do
    sed -i -E \
        -e "s#/home/${U}\\.${P}#/home/user#g" \
        -e "s#${U}\\.${P}#user#g" \
        -e "s#github\\.com/${U}${K}07/[A-Za-z0-9_.-]+#anonymous.4open.science/r/SysJava-8511#g" \
        -e "s#${U}${K}07#anonymous#g" \
        -e "s#[A-Za-z0-9._%+-]*@${S}\\.com#anonymous@example.org#gI" \
        -e "s#${M}#anonymous#gI" \
        -e "s#${U}#user#gI" -e "s#${P}#user#gI" -e "s#${K}#user#gI" -e "s#${S}#anonymous#gI" \
        "$f"
done
