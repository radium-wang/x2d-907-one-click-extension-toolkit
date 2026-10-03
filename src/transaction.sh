# Shared transaction state machine. Backend functions are supplied by a fixed
# generated device prefix or by the offline fault-injection harness.
tx_dirty=0
tx_paused=0
tx_finished=0
tx_restoring=0

tx_restore() {
    [ "$tx_dirty" = 1 ] || return 0
    tx_restoring=1
    backend_same || { backend_log IDENTITY_CHANGED_NO_WRITE; return 91; }
    tx_paused=1
    backend_freeze || { backend_log RESTORE_FREEZE_FAILED; return 92; }
    attempts=0
    while ! backend_pc_clear; do
        # Retry only before any restoration write, and only while the entire
        # candidate is still verified. Never resume partially written code.
        attempts=$((attempts+1))
        [ "$attempts" -lt 10 ] && backend_is_candidate || {
            backend_log RESTORE_PC_BUSY_PROCESS_PAUSED; return 95;
        }
        backend_thaw || return 94
        tx_paused=0
        backend_retry_wait
        tx_paused=1
        backend_freeze || return 92
    done
    # This transaction owns a possibly partial write. Always restore the exact
    # original function before resuming; do not merely reverse selected bytes.
    backend_write_original && backend_is_original || {
        backend_log RESTORE_FAILED_PROCESS_PAUSED_POWER_CYCLE_REQUIRED
        return 93
    }
    tx_dirty=0
    backend_thaw || { backend_log RESTORED_BUT_RESUME_FAILED; return 94; }
    tx_paused=0
    tx_finished=1
    backend_log RESTORED
    backend_log "RESTORED_AT:$(date +%s.%N)"
}

tx_finish() {
    code=$?
    trap - EXIT HUP INT TERM
    if [ "$tx_dirty" = 1 ] && [ "$tx_restoring" = 0 ]; then
        tx_restore || code=99
    elif [ "$tx_paused" = 1 ] && [ "$tx_dirty" = 0 ]; then
        backend_thaw || code=98
    fi
    backend_log "EXIT:$code"
    exit "$code"
}

tx_run() {
    trap tx_finish EXIT
    trap 'exit 97' HUP INT TERM
    backend_preflight || return 10
    tx_paused=1
    backend_freeze || return 11
    backend_pc_clear || return 12
    backend_is_original || return 13
    tx_dirty=1
    backend_write_candidate || return 14
    backend_is_candidate || return 15
    backend_thaw || return 16
    tx_paused=0
    backend_log ACTIVE
    backend_log "ACTIVE_AT:$(date +%s.%N)"
    # Device-local deadline: USB disconnect does not cancel restoration.
    backend_wait || return 17
    tx_restore || return 18
}

# Explicitly requested RAM-only installation. Successful installation ends
# ownership of rollback-on-exit; the saved restore entry remains available.
tx_install_until_restart() {
    trap tx_finish EXIT
    trap 'exit 97' HUP INT TERM
    backend_preflight || return 10
    tx_paused=1
    backend_freeze || return 11
    backend_pc_clear || return 12
    backend_is_original || return 13
    tx_dirty=1
    backend_write_candidate || return 14
    backend_is_candidate || return 15
    backend_thaw || return 16
    tx_paused=0
    tx_dirty=0
    tx_finished=1
    backend_log ACTIVE_UNTIL_RESTART
}
