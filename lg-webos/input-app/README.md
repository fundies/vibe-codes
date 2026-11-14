# Custom input selector — LG 75NANO90UPA (webOS 6.5.3)

Replaces LG's input menu with a self-made app, opened by the physical Input button.

## Pieces (all on writable storage / user space — nothing in the signed rootfs)
- **App**: `com.webosbrew.inputs` — a web app in /media/developer/apps. Static-HTML tiles
  (HDMI 1-4, NVIDIA Shield on HDMI3, Live TV); OK launches `com.webos.app.hdmiN`; Back closes.
  Installed from `com.webosbrew.inputs.ipk` (hand-built webOS ipk: ar of debian-binary +
  control.tar.gz + data.tar.gz, ustar/no-xattrs or the verifier rejects it).
- **Button binding**: `org.webosbrew.inputhook` (installed). Keybind file
  `/home/root/.config/lginputhook/keybinds.json` maps the Input button to exec the launcher.
  The button is matched by **both** keyid `19` and uinput_code `241` — a single one proved
  unreliable across reboots, both together works. inputhook suppresses LG's menu on that key.
- **Launcher**: `/var/lib/open-inputs.sh` — close-then-launch, which force-foregrounds the app
  (a plain relaunch of an already-running instance does NOT come to the front).

## Why each wall mattered (lessons)
- A web app runs *inside* WebAppMgr, so it has no own process — `ps | grep` is always empty; use the screen.
- The first app build failed to render (JS-generated DOM); static-HTML tiles render reliably.
- inputhook matches the uinput_code, not the keyid shown in /tmp/lginput-hook-*.log.
- Launch foregrounding needs close-then-launch for an already-running app.
- A homebrew app can intercept the button but can't get "draw over a live input" privilege
  (that needs trustLevel:trusted — a signed system app), so overlaying LG's input menu app
  was impossible; a standalone app launched fresh is the clean path.

## Revert
- Input button normal: `echo "{}" > /home/root/.config/lginputhook/keybinds.json`
- Remove app: `luna-send -n 1 -f luna://com.webos.appInstallService/dev/remove '{"id":"com.webosbrew.inputs"}'`
- Remove launcher: `rm /var/lib/open-inputs.sh`

## To change the tiles / icon
Edit index.html (tiles are static `<div class="tile" data-app="...">`), re-deploy to
/media/developer/apps/usr/palm/applications/com.webosbrew.inputs/index.html, close+relaunch.
