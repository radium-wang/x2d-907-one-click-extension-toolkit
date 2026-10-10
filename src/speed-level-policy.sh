# App-owned speed selection; known complete functions only, default Medium.
LEVEL=/blackbox/x2d-speed-buff.level
speedLevel=medium
for path in "$LEVEL" "$LEVEL.next"; do [ ! -L "$path" ] || exit 39; done
if [ -e "$LEVEL" ]; then
 [ -f "$LEVEL" ] || exit 39
 speedLevel=$(cat "$LEVEL")
 case "$speedLevel" in low|medium|high) ;; *) exit 39;; esac
fi
speed_config() {
 case "$1" in
 low) CANDIDATE=__LOW_HASH__; SPEED_FILE=$BASE/candidate-low;;
 medium) CANDIDATE=__MEDIUM_HASH__; SPEED_FILE=$BASE/candidate-medium;;
 high) CANDIDATE=4eb555dc16ad54bdcfecd244b63bfea7ee691ce67b8274a1244644392ba15e13; SPEED_FILE=$BASE/candidate;;
 *) return 1;;
 esac
}
speed_config "$speedLevel"
speed_known() {
 case "$1" in __LOW_HASH__|__MEDIUM_HASH__|4eb555dc16ad54bdcfecd244b63bfea7ee691ce67b8274a1244644392ba15e13) return 0;; *) return 1;; esac
}
speed_save() {
 (umask 077; printf '%s\n' "$speedLevel" >"$LEVEL.next" && mv -f "$LEVEL.next" "$LEVEL" && sync)
}
speed_select() {
 [ "$master" = true ] && [ "$ready" = true ] && [ "$active" = true ] || return 1
 target=${action#speed_}
 case "$target" in low|medium|high) ;; *) return 1;; esac
 if [ "$target" = "$speedLevel" ] && { [ "$active" = false ] || [ "$CURRENT" = "$CANDIDATE" ]; }; then return 0; fi
 was_active=$active
 # Cancel boot intent before withdrawing the old function. On interruption or
 # failure remain OFF rather than apply an unconfirmed profile on next boot.
 if [ "$was_active" = true ]; then rm -f "$ENABLED"; sync; restore || return 1; fi
 old_level=$speedLevel
 speedLevel=$target; speed_config "$speedLevel"
 if [ "$was_active" = true ]; then
  if ! speed_install; then speedLevel=$old_level; speed_config "$speedLevel"; return 1; fi
 fi
 if ! speed_save; then
  if [ "$was_active" = true ]; then restore || return 1; fi
  speedLevel=$old_level; speed_config "$speedLevel"; return 1
 fi
 if [ "$was_active" = true ]; then : >"$ENABLED"; sync; fi
}
