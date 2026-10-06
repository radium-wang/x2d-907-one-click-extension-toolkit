#!/system/bin/sh
set -eu
export PATH=/system/bin:/system/xbin:/sbin
export TMPDIR=/tmp
BASE=/system/etc/x2d-speed-buff
D=/tmp/x2d-speed-buff
MASTER=/blackbox/x2d-speed-buff.master
ENABLED=/blackbox/x2d-speed-buff.enabled
AFC=/blackbox/x2d-play-afc.enabled
FEATURE_MASK=${X2D_FEATURE_MASK:-7}
case "$FEATURE_MASK" in 1|2|3|4|5|6|7) ;; *) exit 38;; esac
action=${1:-status}
case "$action" in
 enable) [ "$((FEATURE_MASK & 2))" != 0 ] || exit 38;;
 afc_on) [ "$((FEATURE_MASK & 1))" != 0 ] || exit 38;;
esac
mkdir -p "$D"; chmod 700 "$D"
# The loopback server and the USB restore action share a single transaction lock.
n=0
while ! mkdir "$D/lock" 2>/dev/null; do
 n=$((n+1)); [ "$n" -lt 15 ] || exit 36
 sleep 1
done
trap 'rmdir "$D/lock"' EXIT
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
case "$action" in
 master_on) [ "$ready" = true ]; : >"$MASTER"; master=true;;
 master_off)
  restore
  if [ "$afc" = true ]; then
   odindb-send -s camera -p focus_mode -- E_FocusModes_Afs >/dev/null
   odindb-send -s camera -p focus_mode | grep -q 'E_FocusModes_Afs(1)'
  fi
  rm -f "$MASTER" "$ENABLED" "$AFC" /blackbox/x2d-play-auto-brightness.enabled /blackbox/x2d-play-auto-brightness.available; master=false; afc=false;;
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
printf '{"ready":%s,"active":%s,"master":%s,"afc":%s,"prankIbis":%s,"featureMask":%s,"message":"%s"}\n' "$ready" "$active" "$master" "$afc" "$prankIbis" "$FEATURE_MASK" "$message" >"$D/ui.json"
