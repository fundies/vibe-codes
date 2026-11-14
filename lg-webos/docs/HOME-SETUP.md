# Home replacement + boot-to-HDMI3 — LG 75NANO90UPA (webOS 6.5.3)

## What was done
1. Installed **Luma** v2.16.2 (`com.ecklf.luma`) — native launcher, replaces LG Home.
   - sha256 b313d01bd3bdeef16c9785ccb4372ad2f94728ecf65b80c802516286a9e6a7cd
   - Lives in /media/developer/apps (user space, deletable). NOT rootfs.
2. Enabled Luma **takeover**: bind-mounts Luma's executable over
   /usr/bin/com.webos.app.home (overlay from writable p53 — the signed squashfs is
   NOT modified). Home button now opens Luma, not the LG dashboard.
   - Luma installed its own cold-boot hook: /var/lib/webosbrew/init.d/64-luma-home
3. Installed **boot-to-HDMI3** hook: /var/lib/webosbrew/init.d/70-boot-hdmi3
   - Runs after Luma's hook; waits for SAM, then launches com.webos.app.hdmi3.
   - Result: TV powers on -> HDMI3; press Home -> Luma.

## Boot hook order (/var/lib/webosbrew/init.d, run by run-parts)
  10-debloat     - service debloat (25 masked)
  64-luma-home   - Luma home takeover (reapply mount)
  70-boot-hdmi3  - land on HDMI3

## Revert (all reversible, no systemfs touched)
- Boot to HDMI3 off:   rm /var/lib/webosbrew/init.d/70-boot-hdmi3
- Restore LG Home:     sh /var/lib/luma-home/home.sh disable    (then reboot)
- Uninstall Luma:      disable takeover FIRST, then
    luna-send -n 1 -f luna://com.webos.appInstallService/dev/remove '{"id":"com.ecklf.luma"}'
- Full stock UI:       do all three above, reboot.

## Notes
- Takeover status: sh /var/lib/luma-home/home.sh status
- Luma boot log:   /var/lib/luma-home/boot.log ; HDMI3 hook log: /tmp/boot-hdmi3.log
- Open Luma once after any Luma update so it saves its background/splash.
