# Variables P, START, BOOT, ADDRESS, LENGTH, ORIGINAL, CANDIDATE, PRODUCT,
# WINDOW and D are substituted in a separate, host-validated fixed prefix.
backend_log() { printf '%s\n' "$*"; }
backend_same() {
    [ "$(cat /proc/sys/kernel/random/boot_id)" = "$BOOT" ] &&
    [ "$(awk '{print $22}' /proc/"$P"/stat)" = "$START" ]
}
memory_hash() {
    dd if=/proc/"$P"/mem bs=1 skip="$ADDRESS" count="$LENGTH" 2>/dev/null | sha256sum | awk '{print $1}'
}
backend_is_original() { [ "$(memory_hash)" = "$ORIGINAL" ]; }
backend_is_candidate() { [ "$(memory_hash)" = "$CANDIDATE" ]; }
backend_preflight() {
    backend_same &&
    grep -q ' /tmp tmpfs ' /proc/mounts &&
    [ "$(sha256sum "$D/original" | awk '{print $1}')" = "$ORIGINAL" ] &&
    [ "$(sha256sum "$D/candidate" | awk '{print $1}')" = "$CANDIDATE" ] &&
    [ "$(dd if=/proc/"$P"/mem bs=1 skip="$PRODUCT" count=4 2>/dev/null | od -An -tu4 | tr -d ' \n')" = "${EXPECTED_PRODUCT:-81470}" ] &&
    busybox timeout -t 2 -s KILL awk '/TracerPid:/{n++;if($2!=0)bad++} END{exit(!n||bad)}' /proc/"$P"/task/*/status &&
    backend_is_original
}
backend_freeze() {
    backend_same || return 1
    kill -STOP "$P" || return 1
    n=0
    while [ "$n" -lt 20 ]; do
        if busybox timeout -t 1 -s KILL awk '/State:/{n++;if($2!="T")bad++} END{exit(!n||bad)}' /proc/"$P"/task/*/status; then return 0; fi
        n=$((n+1)); sleep 0.01
    done
    return 1
}
backend_pc_clear() {
    # There are no BL/BLR calls in either replaced instruction range. Check all
    # stopped PCs; refuse if a thread is within the enclosing function or if
    # the kernel refuses to disclose a PC. No speculative in-flight patching.
    busybox timeout -t 2 -s KILL awk -v low="$ADDRESS" -v len="$LENGTH" '
      {n++; p=$NF; if(NF<3||p!~/^0x[0-9a-fA-F]+$/)bad++;
       v=p+0; if(v>=low&&v<low+len)bad++}
      END{exit(!n||bad)}' /proc/"$P"/task/*/syscall
}
backend_write_candidate() {
    backend_same && busybox dd if="$D/candidate" of=/proc/"$P"/mem bs=1 seek="$ADDRESS" count="$LENGTH" conv=notrunc 2>/dev/null
}
backend_write_original() {
    backend_same && busybox dd if="$D/original" of=/proc/"$P"/mem bs=1 seek="$ADDRESS" count="$LENGTH" conv=notrunc 2>/dev/null
}
backend_thaw() { backend_same && kill -CONT "$P"; }
backend_wait() { sleep "$WINDOW"; }
backend_retry_wait() { sleep 0.02; }
