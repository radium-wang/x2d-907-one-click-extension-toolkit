#!/system/bin/sh
set -eu
export PATH=/system/bin:/system/xbin:/sbin
export TMPDIR=/tmp
BASE=/system/etc/x2d-speed-buff
D=/tmp/x2d-speed-buff
MASTER=/blackbox/x2d-speed-buff.master
ENABLED=/blackbox/x2d-speed-buff.enabled
AFC=/blackbox/x2d-play-afc.enabled
EYE_BASELINE=/blackbox/.x2d-play-software/eye-debug-baseline
EYE_TRANSACTION=/blackbox/.x2d-play-software/eye-debug-transaction
EYE_PREF=/blackbox/x2d-play-eye.preference
FEATURE_MASK=${X2D_FEATURE_MASK:-7}
case "$FEATURE_MASK" in 1|2|3|4|5|6|7|8|9|10|11|12|13|14|15) ;; *) exit 38;; esac
action=${1:-status}
case "$action" in
 enable) [ "$((FEATURE_MASK & 2))" != 0 ] || exit 38;;
 afc_on) [ "$((FEATURE_MASK & 1))" != 0 ] || exit 38;;
 eye_on|eye_off|eye_resume) [ "$((FEATURE_MASK & 8))" != 0 ] || exit 38;;
esac
[ ! -L "$D" ] || exit 36
mkdir -p "$D"; chmod 700 "$D"
# Keep the inode permanently; the kernel releases this shared service/USB lock
# even if a worker is killed midway through a persistent Eye transaction.
[ "$(sha256sum /system/bin/toybox | awk '{print $1}')" = 999a0669ef654efbda54bc585c0f3c00643d1af61c985bfb7968cfd2f9aed840 ] || exit 36
[ ! -L "$D/lockfile" ] || exit 36
[ ! -e "$D/lockfile" ] || [ -f "$D/lockfile" ] || exit 36
umask 077
exec 9<>"$D/lockfile"
n=0
while ! /system/bin/toybox flock -x -n 9 2>/dev/null; do
 n=$((n+1)); [ "$n" -lt 15 ] || exit 36
 sleep 1
done
trap '/system/bin/toybox flock -u 9; exec 9>&-' EXIT
trap 'exit 37' HUP INT TERM
ORIGINAL=c8b5407c615b60c05078bc7ba9ada8cf53c905bac17faa59561f948feac0d430
CANDIDATE=4eb555dc16ad54bdcfecd244b63bfea7ee691ce67b8274a1244644392ba15e13
LENGTH=1068
file_sha() { sha256sum "$1" | awk '{print $1}'; }
u64() { dd if=/proc/"$P"/mem bs=1 skip="$1" count=8 2>/dev/null | od -An -tu8 | tr -d ' \n'; }
[ "$(getprop ro.product.device)" = eagle2_ec1706_native ] || exit 30
P=$(pidof camera-service)
case "$P" in ''|*[!0-9]*) exit 31;; esac
START=$(awk '{print $22}' /proc/"$P"/stat)
BOOT=$(cat /proc/sys/kernel/random/boot_id)
BIAS=$(awk '$2=="r-xp"&&$3=="00000000"&&$NF=="/system/lib64/libaaa.so" {split($1,a,"-");printf "%.0f",("0x"a[1])+0-4096}' /proc/"$P"/maps)
case "$BIAS" in ''|*[!0-9]*) exit 32;; esac
ADDRESS=$(awk -v b="$BIAS" 'BEGIN{printf "%.0f",b+705408}')
CURRENT=$(dd if=/proc/"$P"/mem bs=1 skip="$ADDRESS" count="$LENGTH" 2>/dev/null | sha256sum | awk '{print $1}')
# Saved prefix is generated only locally; never accept a foreign process candidate.
if [ "$CURRENT" = "$CANDIDATE" ]; then
 [ -f "$D/identity" ] && [ "$(cat "$D/identity")" = "$BOOT:$P:$START" ] || exit 33
fi
prankIbis=false
[ ! -f /blackbox/.x2d-play-software/prank-ibis ] || prankIbis=true
ready=true; active=false; master=false; afc=false; message='耍起功能已关闭'
[ ! -e "$MASTER" ] || master=true
[ ! -e "$AFC" ] || afc=true
[ "$CURRENT" != "$CANDIDATE" ] || active=true
if [ "$CURRENT" != "$ORIGINAL" ] && [ "$CURRENT" != "$CANDIDATE" ]; then ready=false; message='速度函数未知，拒绝写入'; fi
restore() {
 [ "$CURRENT" != "$CANDIDATE" ] || {
  sh "$D/restore" >"$D/restore.log" 2>&1
  CURRENT=$(dd if=/proc/"$P"/mem bs=1 skip="$ADDRESS" count="$LENGTH" 2>/dev/null | sha256sum | awk '{print $1}')
  [ "$CURRENT" = "$ORIGINAL" ]
 }
 [ "$CURRENT" = "$ORIGINAL" ]
 active=false
}
# Stock SystemObjectImpl masks its debug_options getter to zero when debug_mode
# is false. Read the saved INI value without enabling any hidden debug options.
# Only stock setters write configuration; the file is never edited here.
eye_read() {
 eyeKnown=false
 [ "$(file_sha /system/bin/camera-system)" = bf854a21881148565ff2cc00376426c37a2b82fed94c653abf024e23ed4ceda6 ] || return 1
 [ "$(file_sha /system/bin/odindb-send)" = 4fdf240bd521fbf54ec638617446e4eb8778335734cb36752df6ff1a2336f62b ] || return 1
 [ -f /data/config/system.ini ] && [ ! -L /data/config/system.ini ] || return 1
 eye_saved=$(awk '
 function trim(s){sub(/^[ \t\r]+/,"",s);sub(/[ \t\r]+$/,"",s);return s}
 function flags(s, n,a,i,b,total){
  if(s ~ /^[0-9]+$/){if(length(s)>3 || s+0>127)return -1;return s+0}
  if(s ~ /^HblmTypes::/)sub(/^HblmTypes::/,"",s);else return -1
  n=split(s,a,"|");total=0
  for(i=1;i<=n;i++){
   b=a[i]=="E_DebugOption_EyeDetection"?1:a[i]=="E_DebugOption_FaceDetection"?2:a[i]=="E_DebugOption_Recalibrate"?4:a[i]=="E_DebugOption_Touch"?8:a[i]=="E_DebugOption_TouchPointerHandlers"?16:a[i]=="E_DebugOption_Dcf"?32:a[i]=="E_DebugOption_Browse"?64:a[i]=="E_DebugOption_None"?0:-1
   if(b<0 || (!b && n!=1) || (b && int(total/b)%2))return -1
   total+=b
  }
  return total
 }
 BEGIN{mode=0;options=0;section=0;sections=0;bad=0}
 {line=trim($0);if(line=="" || line ~ /^[;#]/)next
  if(line ~ /^\[/){section=(line=="[Default]");if(section)sections++;next}
  if(!section)next
  eq=index(line,"=");if(!eq)next
  key=trim(substr(line,1,eq-1));value=trim(substr(line,eq+1))
  if(key=="debug_mode"){if(++modes>1)bad=1;if(value=="true" || value=="1")mode=1;else if(value!="false" && value!="0")bad=1}
  if(key=="debug_options"){if(++masks>1)bad=1;options=flags(value);if(options<0)bad=1}
 }
 END{if(bad || sections!=1)exit 1;printf "%d %d\n",mode,options}
 ' /data/config/system.ini) || return 1
 set -- $eye_saved
 [ "$#" = 2 ] || return 1
 eye_mode=$1; eye_options=$2
 eye_reply=$(odindb-send -s system -p debug_mode) || return 1
 eye_effective_mode=$(printf '%s\n' "$eye_reply" | awk '/=[ \t]*(true|false|0|1)[ \t\r]*$/ {n++;sub(/^.*=[ \t]*/,"");sub(/[ \t\r]*$/,"");v=($0=="true"||$0=="1")?1:0} END{if(n!=1)exit 1;print v}') || return 1
 [ "$eye_effective_mode" = "$eye_mode" ] || return 1
 eye_reply=$(odindb-send -s system -p debug_options) || return 1
 eye_effective=$(printf '%s\n' "$eye_reply" | awk '
 function trim(s){sub(/^[ \t\r]+/,"",s);sub(/[ \t\r]+$/,"",s);return s}
 function flags(s,n,a,i,b,total){n=split(s,a,"|");total=0
  for(i=1;i<=n;i++){a[i]=trim(a[i]);b=a[i]=="E_DebugOption_EyeDetection"?1:a[i]=="E_DebugOption_FaceDetection"?2:a[i]=="E_DebugOption_Recalibrate"?4:a[i]=="E_DebugOption_Touch"?8:a[i]=="E_DebugOption_TouchPointerHandlers"?16:a[i]=="E_DebugOption_Dcf"?32:a[i]=="E_DebugOption_Browse"?64:a[i]=="E_DebugOption_None"?0:-1
   if(b<0 || (!b && n!=1) || (b && int(total/b)%2))return -1;total+=b}
  return total}
 /=/ {v=trim(substr($0,index($0,"=")+1));
  if(v ~ /\([0-9]+\)$/){names=v;sub(/\([0-9]+\)$/, "",names);sub(/^.*\(/,"",v);sub(/\)$/, "",v)
   if(names ~ /^\[.*\]$/){sub(/^\[/,"",names);sub(/\]$/,"",names)}
   if(flags(names)!=v+0)next}
  if(v ~ /^[0-9]+$/ && length(v)<=3 && v+0<=127){n++;value=v+0}}
 END{if(n!=1)exit 1;print value}' ) || return 1
 eye_expected=0; [ "$eye_mode" = 0 ] || eye_expected=$eye_options
 [ "$eye_effective" = "$eye_expected" ] || return 1
 eyeActive=false
 [ "$eye_mode" != 1 ] || [ "$((eye_options & 1))" = 0 ] || eyeActive=true
 eyeKnown=true
}
eye_baseline_read() {
 [ -f "$EYE_BASELINE" ] && [ ! -L "$EYE_BASELINE" ] || return 1
 eye_original=$(awk 'NR==1 && NF==3 && $1=="1" && $2 ~ /^[01]$/ && $3 ~ /^[0-9]+$/ && length($3)<=3 && $3+0<=127 {valid=1;v=$2 " " ($3+0)} END{if(NR!=1 || !valid)exit 1;print v}' "$EYE_BASELINE") || return 1
 set -- $eye_original
 eye_original_mode=$1; eye_original_options=$2
}
eye_snapshot() {
 if [ -e "$EYE_BASELINE" ] || [ -L "$EYE_BASELINE" ]; then eye_baseline_read; return $?; fi
 [ -d /blackbox/.x2d-play-software ] && [ ! -L /blackbox/.x2d-play-software ] || return 1
 (umask 077; set -C; printf '1 %s %s\n' "$eye_mode" "$eye_options" >"$EYE_BASELINE") || return 1
 sync
 eye_baseline_read
}
eye_preference_read() {
 eye_preference_path=${1:-$EYE_PREF}
 [ -f "$eye_preference_path" ] && [ ! -L "$eye_preference_path" ] || return 1
 eye_preference=$(awk 'NR==1 && ($0=="0" || $0=="1") {valid=1;v=$0} END{if(NR!=1 || !valid)exit 1;print v}' "$eye_preference_path")
}
eye_preference_write() {
 eye_next_recover || return 1
 [ ! -L "$EYE_PREF" ] && [ ! -e "$EYE_PREF.next" ] && [ ! -L "$EYE_PREF.next" ] || return 1
 (umask 077; set -C; printf '%s\n' "$1" >"$EYE_PREF.next") || return 1
 mv "$EYE_PREF.next" "$EYE_PREF"
 sync
}
eye_transaction_read() {
 eye_transaction_path=${1:-$EYE_TRANSACTION}
 [ -f "$eye_transaction_path" ] && [ ! -L "$eye_transaction_path" ] || return 1
 eye_transaction=$(awk 'NR==1 && NF==5 && $1=="1" && $2 ~ /^[01]$/ && $4 ~ /^[01]$/ && $3 ~ /^[0-9]+$/ && length($3)<=3 && $3+0<=127 && $5 ~ /^[0-9]+$/ && length($5)<=3 && $5+0<=127 {valid=1;v=$2 " " ($3+0) " " $4 " " ($5+0)} END{if(NR!=1 || !valid)exit 1;print v}' "$eye_transaction_path") || return 1
 set -- $eye_transaction
 eye_before_mode=$1; eye_before_options=$2; eye_after_mode=$3; eye_after_options=$4
}
eye_transaction_matches() {
 [ "$eye_mode:$eye_options" != "$eye_before_mode:$eye_before_options" ] || return 0
 [ "$eye_mode:$eye_options" != "$eye_after_mode:$eye_after_options" ] || return 0
 # The only partial states are determined by eye_write ordering.
 if [ "$eye_after_mode" = 0 ]; then [ "$eye_mode:$eye_options" = "0:$eye_before_options" ]
 else [ "$eye_mode:$eye_options" = "$eye_before_mode:$eye_after_options" ]; fi
}
eye_owned_state() {
 if [ "$eye_original_mode" = 0 ]; then
  [ "$eye_mode:$eye_options" = "0:$eye_original_options" ] || [ "$eye_mode:$eye_options" = "1:1" ]
 else
  [ "$eye_mode" = 1 ]
 fi
}
eye_next_recover() {
 if [ -e "$EYE_TRANSACTION.next" ] || [ -L "$EYE_TRANSACTION.next" ]; then
  eye_baseline_read && eye_transaction_read "$EYE_TRANSACTION.next" || return 1
  [ "$eye_before_mode:$eye_before_options" = "$eye_mode:$eye_options" ] || return 1
  if [ "$eye_original_mode" = 0 ]; then
   [ "$eye_after_mode:$eye_after_options" = "0:$eye_original_options" ] || [ "$eye_after_mode:$eye_after_options" = "1:1" ] || return 1
  else
   [ "$eye_after_mode" = 1 ] && [ "$((eye_before_options & 126))" = "$((eye_after_options & 126))" ] || return 1
  fi
  if ! eye_owned_state; then eye_transaction_read && eye_transaction_matches || return 1; fi
  rm -f "$EYE_TRANSACTION.next"
 fi
 if [ -e "$EYE_PREF.next" ] || [ -L "$EYE_PREF.next" ]; then
  eye_baseline_read && eye_preference_read "$EYE_PREF.next" && eye_owned_state || return 1
  [ ! -e "$EYE_TRANSACTION" ] && [ ! -L "$EYE_TRANSACTION" ] || return 1
  [ "$eyeActive" = "$([ "$eye_preference" = 1 ] && printf true || printf false)" ] || return 1
  rm -f "$EYE_PREF.next"
 fi
}
eye_transaction_save() {
 eye_next_recover || return 1
 [ ! -L "$EYE_TRANSACTION" ] && [ ! -e "$EYE_TRANSACTION.next" ] && [ ! -L "$EYE_TRANSACTION.next" ] || return 1
 if [ -e "$EYE_TRANSACTION" ]; then eye_transaction_read && eye_transaction_matches || return 1; fi
 (umask 077; set -C; printf '1 %s %s %s %s\n' "$eye_mode" "$eye_options" "$1" "$2" >"$EYE_TRANSACTION.next") || return 1
 mv "$EYE_TRANSACTION.next" "$EYE_TRANSACTION"
 sync
}
eye_write() {
 eye_target_mode=$1; eye_target_options=$2
 eye_transaction_save "$eye_target_mode" "$eye_target_options" || return 1
 # Deactivate debug mode before restoring hidden options; never activate those
 # options briefly through a write-before-disable ordering.
 if [ "$eye_target_mode" = 0 ]; then
  odindb-send -s system -p debug_mode -- false >/dev/null || return 1
  eye_read && [ "$eye_mode" = 0 ] || return 1
 fi
 eye_step_mode=$eye_mode
 odindb-send -s system -p debug_options -- "$eye_target_options" >/dev/null || return 1
 eye_read && [ "$eye_mode" = "$eye_step_mode" ] && [ "$eye_options" = "$eye_target_options" ] || return 1
 if [ "$eye_target_mode" = 1 ]; then odindb-send -s system -p debug_mode -- true >/dev/null || return 1; fi
 eye_read || return 1
 [ "$eye_mode" = "$eye_target_mode" ] && [ "$eye_options" = "$eye_target_options" ] || return 1
 rm -f "$EYE_TRANSACTION"
 eyeReady=true; eyeIssue=none
}
eye_restore_baseline() {
 if [ ! -e "$EYE_BASELINE" ] && [ ! -L "$EYE_BASELINE" ]; then
  [ ! -e "$EYE_PREF" ] && [ ! -L "$EYE_PREF" ] && [ ! -e "$EYE_TRANSACTION" ] && [ ! -L "$EYE_TRANSACTION" ] && [ ! -e "$EYE_TRANSACTION.next" ] && [ ! -L "$EYE_TRANSACTION.next" ] && [ ! -e "$EYE_PREF.next" ] && [ ! -L "$EYE_PREF.next" ]
  return $?
 fi
 eye_baseline_read && eye_read || return 1
 eye_next_recover || return 1
 eye_partial=false
 if [ -e "$EYE_TRANSACTION" ] || [ -L "$EYE_TRANSACTION" ]; then
  eye_transaction_read && eye_transaction_matches || return 1
  eye_partial=true
 fi
 if [ "$eye_original_mode" = 0 ]; then
  # A user may have changed other debug options while this feature was active.
  # Stop rather than disable those options or activate the old hidden ones.
  if [ "$eye_mode" = 1 ] && [ "$((eye_options & 126))" != 0 ]; then return 1; fi
  if [ "$eye_mode" = 0 ] && [ "$eye_options" != "$eye_original_options" ] && [ "$eye_partial" != true ]; then return 1; fi
  eye_write 0 "$eye_original_options"
 else
  [ "$eye_mode" = 1 ] || return 1
  eye_write "$eye_mode" "$(((eye_options & 126) | (eye_original_options & 1)))"
 fi
}
eye_apply() {
 eye_choice=$1
 eye_read && eye_snapshot || return 1
 if [ "$eye_original_mode" = 0 ]; then
  if [ "$eye_mode" = 1 ] && [ "$((eye_options & 126))" != 0 ]; then return 1; fi
  if [ "$eye_mode" = 0 ] && [ "$eye_options" != "$eye_original_options" ]; then return 1; fi
  if [ "$eye_choice" = 1 ]; then eye_write 1 1 || return 1
  else eye_write 0 "$eye_original_options" || return 1; fi
 else
  [ "$eye_mode" = 1 ] || return 1
  eye_write 1 "$(((eye_options & 126) | eye_choice))" || return 1
 fi
 [ "$eyeActive" = "$([ "$eye_choice" = 1 ] && printf true || printf false)" ] || return 1
 # Once the setting has returned to its original state, relinquish ownership.
 # A later user change must never be overwritten using a stale old snapshot.
 if [ "$eye_mode" = "$eye_original_mode" ] && [ "$((eye_options & 1))" = "$((eye_original_options & 1))" ]; then
  rm -f "$EYE_PREF" "$EYE_BASELINE"
 else
  eye_preference_write "$eye_choice"
 fi
}
eye_conflict() {
 if [ "$eye_original_mode" = 0 ]; then
  [ "$eye_mode" != 1 ] || [ "$((eye_options & 126))" = 0 ] || return 0
  [ "$eye_mode" != 0 ] || [ "$eye_options" = "$eye_original_options" ] || return 0
 else
  [ "$eye_mode" = 1 ] || return 0
 fi
 return 1
}
eye_reject() {
 eyeReady=false
 if [ -e "$EYE_TRANSACTION" ] && eye_transaction_read && eye_transaction_matches; then eyeIssue=incomplete
 else [ "$eyeIssue" != none ] || eyeIssue=unavailable; fi
}
eyeReady=false; eyeKnown=false; eyeActive=false; eyeEnabled=false; eyeRestored=false; eyeIssue=none
if [ "$((FEATURE_MASK & 8))" != 0 ]; then
 if eye_read; then eyeReady=true; else eyeIssue=unavailable; fi
 if [ -e "$EYE_BASELINE" ] || [ -L "$EYE_BASELINE" ]; then
  if eye_baseline_read; then
   if [ "$eyeReady" = true ] && eye_conflict; then eyeReady=false; eyeIssue=changed; fi
  else eyeReady=false; eyeIssue=unavailable; fi
 fi
 if [ -e "$EYE_PREF" ] || [ -L "$EYE_PREF" ]; then
  if eye_preference_read; then
   [ "$eye_preference" = 0 ] || eyeEnabled=true
   if ! eye_baseline_read; then eyeReady=false; eyeIssue=unavailable; fi
  else eyeReady=false; eyeIssue=unavailable; fi
 fi
 if [ -e "$EYE_TRANSACTION" ] || [ -L "$EYE_TRANSACTION" ]; then
  eyeReady=false
  if eye_transaction_read && eye_transaction_matches; then eyeIssue=incomplete; else eyeIssue=unavailable; fi
 fi
 if [ -e "$EYE_TRANSACTION.next" ] || [ -L "$EYE_TRANSACTION.next" ] || [ -e "$EYE_PREF.next" ] || [ -L "$EYE_PREF.next" ]; then eyeReady=false; eyeIssue=incomplete; fi
fi
case "$action" in
 master_on)
  [ "$ready" = true ]
  if [ "$((FEATURE_MASK & 8))" != 0 ] && { [ -e "$EYE_PREF" ] || [ -L "$EYE_PREF" ]; }; then
   if eye_baseline_read && eye_preference_read && eye_apply "$eye_preference"; then : >"$MASTER"; master=true
   else eye_reject; fi
  else
   : >"$MASTER"; master=true
  fi
  ;;
 master_off)
  if [ "$((FEATURE_MASK & 8))" = 0 ] || eye_restore_baseline; then
   if [ "$((FEATURE_MASK & 8))" != 0 ]; then rm -f "$EYE_PREF" "$EYE_BASELINE"; fi
   restore
   if [ "$afc" = true ]; then
    odindb-send -s camera -p focus_mode -- E_FocusModes_Afs >/dev/null
    odindb-send -s camera -p focus_mode | grep -q 'E_FocusModes_Afs(1)'
   fi
   rm -f "$MASTER" "$ENABLED" "$AFC" /blackbox/x2d-play-auto-brightness.enabled /blackbox/x2d-play-auto-brightness.available
   master=false; afc=false; eyeEnabled=false
  else
   eye_reject
  fi
  ;;
 eye_on|eye_off)
  eye_choice=0; [ "$action" != eye_on ] || eye_choice=1
  if [ "$master" = true ] && [ "$ready" = true ] && [ "$eyeReady" = true ] && eye_apply "$eye_choice"; then
   eyeEnabled=false; [ "$eye_choice" = 0 ] || eyeEnabled=true
  else eye_reject; fi;;
 eye_resume)
  [ "$master" = true ] && [ "$ready" = true ] && [ "$eyeReady" = true ] || exit 39
  if [ -e "$EYE_PREF" ] || [ -L "$EYE_PREF" ]; then eye_baseline_read && eye_preference_read && eye_apply "$eye_preference" || exit 39; fi;;
 eye_restore)
  if [ -e "$EYE_PREF" ] || [ -L "$EYE_PREF" ]; then eye_preference_read || exit 39; fi
  eye_restore_baseline || exit 39
  rm -f "$EYE_PREF" "$EYE_TRANSACTION" "$EYE_BASELINE"
  eyeEnabled=false; eyeRestored=true;;
 afc_on)
  [ "$master" = true ]
  odindb-send -s camera -p focus_mode -- E_FocusModes_Afc >/dev/null
  odindb-send -s camera -p focus_mode | grep -q 'E_FocusModes_Afc(2)'
  : >"$AFC"; afc=true;;
 afc_off)
  odindb-send -s camera -p focus_mode -- E_FocusModes_Afs >/dev/null
  odindb-send -s camera -p focus_mode | grep -q 'E_FocusModes_Afs(1)'
  rm -f "$AFC"; afc=false;;
 disable) restore; rm -f "$ENABLED";;
 enable)
  [ "$master" = true ] && [ "$ready" = true ]
  if [ "$CURRENT" = "$ORIGINAL" ]; then
   [ "$(file_sha /system/lib64/libaaa.so)" = feef8a8dc3a27395e47232c2b25a5da7a7ab335922fbb527e637c439e35bcec7 ]
   AF_PTR_ADDR=$(awk -v b="$BIAS" 'BEGIN{printf "%.0f",b+10680832}')
   AF=$(u64 "$AF_PTR_ADDR")
   case "$AF" in ''|*[!0-9]*) exit 34;; esac
   for offset in 2464 2512 2560; do
    ptr=$(awk -v a="$AF" -v o="$offset" 'BEGIN{printf "%.0f",a+o}')
    # Positive finite IEEE754 double <= 1.5 (low word first).
    dd if=/proc/"$P"/mem bs=1 skip="$ptr" count=8 2>/dev/null | od -An -tu4 | awk 'NF==2 {ok=($2<1073217536||($2==1073217536&&$1==0));n++} END{exit(!(n==1&&ok))}'
   done
   cp "$BASE/original" "$D/original"; cp "$BASE/candidate" "$D/candidate"
   printf 'P=%s\nSTART=%s\nBOOT=%s\nADDRESS=%s\nLENGTH=%s\nORIGINAL=%s\nCANDIDATE=%s\nD=%s\n' "$P" "$START" "$BOOT" "$ADDRESS" "$LENGTH" "$ORIGINAL" "$CANDIDATE" "$D" >"$D/prefix"
   cat "$D/prefix" "$BASE/backend" "$BASE/transaction" >"$D/restore"
   cat >>"$D/restore" <<'RESTORE'
backend_same || exit 81
if backend_is_original; then exit 0; fi
backend_is_candidate || exit 82
tx_dirty=1
trap tx_finish EXIT
trap 'exit 97' HUP INT TERM
tx_restore
exit $?
RESTORE
   cat "$D/prefix" "$BASE/backend" "$BASE/transaction" >"$D/install"
   printf '\ntx_install_until_restart\nexit $?\n' >>"$D/install"
   printf '%s' "$BOOT:$P:$START" >"$D/identity"
   sh "$D/install" >"$D/install.log" 2>&1
   CURRENT=$(dd if=/proc/"$P"/mem bs=1 skip="$ADDRESS" count="$LENGTH" 2>/dev/null | sha256sum | awk '{print $1}')
   [ "$CURRENT" = "$CANDIDATE" ]
  fi
  : >"$ENABLED"; active=true;;
 status) ;;
 *) exit 35;;
esac
if [ "$active" = true ]; then message='对焦加速 buff 已开启：×3 / ×3 / ×2'
elif [ "$master" = true ] && [ "$ready" = true ]; then message='原厂速度；可开启对焦加速 buff'; fi
printf '{"ready":%s,"active":%s,"master":%s,"afc":%s,"eyeReady":%s,"eyeKnown":%s,"eyeActive":%s,"eyeEnabled":%s,"eyeRestored":%s,"eyeIssue":"%s","prankIbis":%s,"featureMask":%s,"message":"%s"}\n' "$ready" "$active" "$master" "$afc" "$eyeReady" "$eyeKnown" "$eyeActive" "$eyeEnabled" "$eyeRestored" "$eyeIssue" "$prankIbis" "$FEATURE_MASK" "$message" >"$D/ui.json"
