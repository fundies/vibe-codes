#!/bin/sh
# webosbrew debloat — runtime-mask non-critical services. Reversible: delete this
# file and reboot (masks live only in /run tmpfs; nothing in rootfs/systemfs is touched).
# Keeps: compositor (surface-manager), sam, ls-hubd, luna, video/pq/panel, audio,
# input (lginput2/eim), network (connman), db8/settings, micom, ssh, logging.

LOG=/tmp/debloat.log
echo "[debloat] $(date) start" > "$LOG"

DISABLE="
contentminer
preload-manager
iot-client
voiceconductor
voiceinput
nudge
bugreportd
miracast
second-screen-gateway
ssdp-discovery-lgtv
webos-sddp
dmr
dmost
remotelogger
rdxd
uploadd
pacrunner
tvlink-network-proxy
tvlinkcmdprocessor
aiservice
user-context-manager
crashreportd
sic-dbg-monitor
avahi-adaptor
avahi-daemon
"

for u in $DISABLE; do
  if systemctl list-unit-files "${u}.service" >/dev/null 2>&1; then
    systemctl mask --runtime --now "${u}.service" >>"$LOG" 2>&1 \
      && echo "[debloat] masked ${u}" >>"$LOG" \
      || echo "[debloat] FAILED ${u}" >>"$LOG"
  else
    echo "[debloat] absent ${u}" >>"$LOG"
  fi
done

# stop stray non-service processes (ads/casting) if present
for p in admanager appcasting airplay airplay-adaptor; do
  pkill -x "$p" 2>/dev/null && echo "[debloat] killed $p" >>"$LOG"
done
echo "[debloat] done" >>"$LOG"
