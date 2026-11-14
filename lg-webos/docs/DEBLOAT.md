# webOS debloat — LG 75NANO90UPA (webOS 6.5.3)

Mechanism: runtime systemd masks (`/run` tmpfs) applied each boot by
`/var/lib/webosbrew/init.d/10-debloat` (run via webosbrew `run-parts`).
**Touches nothing in the signed chain or read-only rootfs.** Masks live in tmpfs.

## Revert
- All at once: `rm /var/lib/webosbrew/init.d/10-debloat` then reboot.
- One service: `systemctl unmask <name>.service && systemctl start <name>.service`
  (masks also clear on any reboot; the script reapplies them).

## Disabled (25 services + stray procs)
Tracking/telemetry: contentminer (ACR), bugreportd, crashreportd, remotelogger, rdxd, uploadd, sic-dbg-monitor
Ads/promos: nudge, admanager (proc)
Preloading: preload-manager
Voice/mic: voiceconductor, voiceinput
Cloud/AI/profiling: iot-client, aiservice, user-context-manager
Casting/sharing: miracast, second-screen-gateway, dmr, dmost, appcasting/airplay (procs)
Discovery/mDNS chatter: ssdp-discovery-lgtv, webos-sddp, avahi-daemon, avahi-adaptor, pacrunner
Remote app control: tvlink-network-proxy, tvlinkcmdprocessor

## Kept (load-bearing)
surface-manager, sam, ls-hubd, luna-sys-service, videooutputd, pqcontroller,
panelcontroller, lginput2/eim (input), audio chain (audiod/pulseaudio/umediaserver),
connman (network+SSH), db8/settings/configd, micom, notificationmgr, maliit (keyboard),
logging, crash capture (crashd local). Bluetooth KEPT (Magic Remote may need BLE).

## Not touched (needs your call)
- Bluetooth stack — disable only if you use a basic IR remote, not a Magic Remote.
- Tuner/DVR (iepg, rec-*, tv-reservation, dvbcim, broadcast-conf, livepick) — disable
  only if you never use antenna/cable.
- Unknown units (socts, qosm, asc, asm, nabs, cbox, dpp, gm, nopd) — left alone on purpose.

## Pre-existing failures (NOT caused by this; benign)
accountmanager (no LG account), dropbear (webosbrew uses openssh), livepick, kadpd.
