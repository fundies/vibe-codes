# Transparent overlay over live HDMI — compositor RE + live protocol test

**Question:** can a homebrew app draw a transparent/partial overlay *on top of live
HDMI video* (like LG's own input menu), given a dev **web** app composites to black?

**Answer: yes — the mechanism exists and is NOT trust-gated.** It is a *native*
Wayland capability, not available to web (WAM) apps. Proven both statically (Ghidra)
and empirically (live protocol calls from an unprivileged client).

## How the TV does video-behind-UI
`libWebOSCoreCompositor` (Qt/QtWayland) implements the `wl_webos_foreign` protocol:
- A client that owns video calls **`export_element`** → compositor creates a
  `WebOSExported`, assigns it a window id (`_Window_Id_N`), returns it via the
  `window_id_assigned` event.
- Another client calls **`import_element(window_id)`** → gets a `wl_webos_imported`,
  then **`attach_punchthrough`** to make the video show through a region of its surface.
This is exactly what LG's input overlay uses. A web app can't speak it, so a
transparent web app just shows the opaque black UI plane → "black screen".

## Protocol map (from the TV's libwayland-webos-client, via ctypes introspection)
```
wl_webos_foreign  v1:   [0]destroy  [1]export_element(nou)  [2]import_element(nsu)
wl_webos_exported v1:   [1]set_exported_window(oo) [2]set_crop_region(ooo)
                        [3]set_property(ss)   evt[0]window_id_assigned(su)
wl_webos_imported v1:   [0]set_surface_alignment(u) [2]attach_punchthrough(s)
                        [3]detach_punchthrough [4]attach_surface(o) [6]set_z_index(i)
                        evt[0]destination_region_changed(uu) [1]punchthrough_attached(s) ...
```

## Live test results (unprivileged client, no app-id / no trust token)
Compositor socket `/tmp/xdg/wayland-0` (root:composit). Test client = plain Python
driving the TV's own `libwayland-client.so.0` + `libwayland-webos-client.so.1` via
ctypes. No compiler needed on the TV.

1. **Registry** offers `wl_webos_foreign`, `wl_webos_shell`,
   `wl_webos_surface_group_compositor` to an anonymous client — no error.
2. **export_element** from the anonymous client → `window_id_assigned: _Window_Id_2`
   (type 0 = video). Compositor created a `WebOSExported` for a random client, no gate.
3. **import_element("_Window_Id_1")** → success; compositor returned
   `destination_region_changed(1920,1080)`. So `_Window_Id_1` is the *live* HDMI/Shield
   video surface and an unprivileged client can import it.
4. import of a non-existent id → clean `No matching WebOSExported` error. So the
   compositor validates *existence* of the id, but **never privilege** — no app-id,
   trust-level, or permission check anywhere in export or import.

Ghidra confirms the same statically: the `export_element`/`import_element` handlers
and the `WebOSExported`/`WebOSImported` classes contain no app-id/trust/permission
check; the compositor's only "not allowed" string belongs to an unrelated function.

## What a real overlay app would do (native, ~a few hundred lines of C or ctypes)
1. bind `wl_compositor`, `wl_webos_foreign`, `wl_webos_shell`.
2. create a surface; give it a shell role via `wl_webos_shell` (fullscreen card).
3. draw UI into a wl_shm ARGB buffer, leaving a transparent hole where video goes.
4. `import_element("_Window_Id_1")`, `attach_punchthrough`, `set_z_index`,
   position via `set_exported_window`/the imported destination region.
5. commit + frame loop.
Everything above is reachable by an ordinary (homebrew) client — no firmware/rootfs
change, no signed component touched. It must be native code, not a web app.

## Caveats
- The live video id (`_Window_Id_1` today) is assigned at runtime; discover it rather
  than hardcode (import by trying `_Window_Id_1..N`, or read it from the foreground
  input's own export). It persists while that input is up.
- `wl_webos_shell` window-type/layer gating (surface-manager QML) wasn't needed for the
  foreign path and wasn't separately audited; the punch-through path above is sufficient.
- Definitive visual proof = building the minimal native client and mapping it; not done
  here to avoid disrupting the live screen.

---

## Build progress (native overlay app)

**Vehicle solved.** A standalone Wayland client is NOT composited by LSM — it only
shows surfaces for SAM-registered apps. So the overlay is packaged as a native webOS
app `com.webosbrew.overlay` (see `overlay/`): appinfo type `native`, `main=run.sh`,
`run.sh` execs `/usr/bin/python overlay.py` (the ctypes Wayland client). Built into an
ipk with `build_ipk.py` (ar members need mtime 0 + mode `100644`, gzip mtime 0, else
`dev/install` reports "ipk verified failed") and dev-installed; SAM lists and launches it.
Under SAM the client connects (socket `/tmp/xdg/wayland-0`), `APPID` is in the env,
runs as non-root (so use a per-pid `/tmp` buffer file, not a root-owned one).

**The commit-kill bug — solved.** The client was hard-closed (EPIPE, no protocol error)
not by any auth gate but by one bad request: **`wl_webos_shell_surface.set_size`
(opcode 4) hard-closes the client on this compositor.** Removing it, the full sequence
survives commit cleanly:
  create_surface → get_shell_surface → set_property(appId) →
  set_property(_WEBOS_WINDOW_TYPE,_WEBOS_WINDOW_TYPE_CARD) → set_state → shm buffer →
  attach → damage → commit.
The buffer's 1920x1080 dimensions define the surface size, so set_size is redundant.

**Surface-group layering (how LG overlays UI on live video).** LG's input apps
(`com.webos.app.externalinput.av1`, native, `transparent:true`) own a `windowGroup`
with layers: UI `layer1` at z=1, video/data/subtitle layers at negative z. Protocol:
  wl_webos_surface_group_compositor.create_surface_group(new_id, owner_surface, name)
  wl_webos_surface_group.create_layer(new_id, name, z) / attach(surface, layer_name)
  wl_webos_surface_group_layer.set_z_index(i)
Reference impl is `/usr/bin/com.webos.app.inputcommon` (Qt5/QML + libwebos-platform-
interface); it uses the Qt `webos` wayland shell integration which does the group setup.

**Status:** client is fixed and staged on the TV (set_size removed), not yet launched.
Confirming it actually displays requires one SAM launch (which briefly foregrounds the
app = screen leaves the current input). Remaining work after "does it show": draw the
real UI into the shm buffer, and bring live video behind it via either surface-group
layers (LG's way) or import_element+attach_punchthrough (proven available).

---

## Display blocker: webOS native-app LS2 security handshake (where the build stands)

To get LSM to actually *show* the surface, SAM must foreground the app, which only
happens after the app completes the native-app lifecycle: call
`luna://com.webos.applicationManager/registerApp` (subscription). LG's native apps do
this via linked `libluna-service2` (the `luna-send` CLI is root-only, mode `rwx------`,
and SAM runs apps under a per-launch sandbox uid — e.g. 6714 — so the CLI can't be used).

Reproduced the registerApp call via `libluna-service2` + glib from Python/ctypes, but
`LSRegister`/`LSRegisterApplicationService` fail with **"Invalid permissions for
com.webosbrew.overlay"**, even when SAM-launched:
- The dev install created the app's LS2 **manifest + client-permissions** but **no
  `roles.d` role file** (the working web app `com.webosbrew.inputs` has one). Authored a
  role modeled on inputs and repaired the manifest (`roleFiles`), reloaded the hub
  (`ls-control scan-services`) — still denied.
- Root cause: LS2 binds a client to its appId/role via a **security token the sandbox
  launcher injects** into blessed native apps (what `libwebos-platform-interface` / the
  Qt `webos` platform plugin consume). A hand-rolled Python process doesn't present it,
  so the hub refuses the registration regardless of role files.

**Net:** every layer below the display is solved (packaging, SAM launch, Wayland connect,
surface create + commit with the `set_size` fix). The last wall is **webOS's app-sandbox
LS2 authentication**, not the overlay mechanism. Finishing a working visible overlay in
Python means reverse-engineering and replicating that security-token handshake — open-
ended, and only testable via screen-disrupting launches. The "proper" alternative is a
Qt/C++ native app built against LG's platform plugin (needs an ARM cross-toolchain +
build), which gets the handshake for free. The overlay *capability* itself is proven and
ungated; this remaining work is webOS runtime plumbing.

Installed test app `com.webosbrew.overlay` is dormant (runs only if launched); safe to
leave or remove (`luna://com.webos.appInstallService/dev/remove`).

---

## Compiling path (zig) — cracks the native-app runtime handshake

No compiler on the TV, so: `zig cc -target arm-linux-gnueabi.2.17` cross-compiles C to
the TV's exact ABI (32-bit ARM EABI5 **soft-float**, glibc≤2.17, interp /lib/ld-linux.so.3,
matching /usr/bin/com.webos.app.inputcommon). A hello binary ran on the TV; the overlay
client (`overlay/overlay.c`) links against the TV's own libs (wayland-client,
wayland-webos-client, luna-service2, glib — pulled locally). Deliverables in `overlay/`.

**This solved the blockers the Python path could not:**
1. **LS2 identity (was "Invalid permissions"):** the hub authenticates a client by its
   executable path. `/usr/bin/python` is shared and unusable in a role; a compiled binary
   at `/media/developer/apps/.../com.webosbrew.overlay/overlay` has a unique path. Adding
   an LS2 role with that `exeName` (the dev install omits the `roles.d` file for a
   hand-rolled native app — author it + fix the manifest + `ls-control scan-services`) →
   **`LSRegister` succeeds**.
2. **Native lifecycle:** with a handle, `LSCall luna://com.webos.applicationManager/registerApp`
   (glib main loop via `LSGmainAttach` + `g_main_context_iteration`) returns
   **`{"event":"registered","returnValue":true}`**. The CLI `luna-send` can't be used — it's
   root-only (rwx------) and SAM runs apps under a per-launch sandbox uid (e.g. 6714).
3. **`set_size` still hard-closes** (as on the Python path) — omit it.
After all this, SAM's `running` list includes `com.webosbrew.overlay` — the app launches,
registers, and is considered running.

### Remaining blocker (where it stands)
The running app's surface is **never promoted to the foreground/fullscreen window** —
compositor `getForegroundAppInfo` stays on the current input, no LSM `NL_VSC` for the
overlay, SAM logs `NL_APP_LAUNCH_BEGIN` but never completes to foreground. The displayed
model is `StarfishFullscreenWindowModel` whose filter is literally `surfaceItem.fullscreen`;
`set_state` → `WebOSShellSurface::setState(Qt::WindowState)` → `WebOSSurfaceItem::setState`,
but neither `set_state(3)` nor `set_state(4 = Qt::WindowFullScreen)`, before or after map,
made `surfaceItem.fullscreen` true / promoted the surface. `WebOSSurfaceItem::setFullscreen`
is driven by `WebOSCoreCompositor::setFullscreen` (the view controller), not directly by the
client — so the gap is the compositor's surface→appId→foreground promotion for a launched
native app.

**Next step to finish:** decompile the foreground-promotion path in
`libWebOSCoreCompositor` / the `WebOSCompositor` QML (how a launched appId's surface becomes
`views.fullscreen.currentItem`), or diff the Wayland/shell sequence against a working native
app (Luma) to find the missing property/call. Everything up to that point is working and
reproducible. Gnarly jail/log notes: the jail shares real `/tmp`, so a root-owned
`/tmp/overlay.log` silently blocks the uid-6714 app's `freopen` — `rm` it before each run.

---

## The exact display gate (decompiled) — and why it's the last mile

Decompiled `libWebOSCoreCompositor` (Ghidra headless, JDK25) + read the compositor QML.
A launched app's surface is shown only when the compositor promotes it to the fullscreen
view. That promotion is `WebOSCompositorBase/views/FullscreenView.qml` → `checkFullscreen(item)`,
run on `onSurfaceMapped` / `onFullscreenRequested`:

    if (!item.isProxy() && !item.isPartOfGroup() &&
        (item.type == "_WEBOS_WINDOW_TYPE_CARD" || "_WEBOS_WINDOW_TYPE_RESTRICTED") &&
        item.displayAffinity == compositorWindow.displayId) {
        item.state = Qt.WindowFullScreen; item.fullscreen = true;  // -> enters model, shown
    } else console.warn("request ignored");

So four conditions: not a proxy, not in a surface group, window type CARD, and
**displayAffinity == the display's id**. Surface props flow via
`wl_webos_shell_surface.set_property` → `WebOSSurfaceItem::updateProperties(QMap)` which
dispatches keys by name: `appId`, `_WEBOS_WINDOW_TYPE`, `_WEBOS_WINDOW_CLASS`,
`displayAffinity` (15-char key → `setDisplayAffinity`), `windowPosition`, etc. The client
now sets `appId`, `_WEBOS_WINDOW_TYPE=_WEBOS_WINDOW_TYPE_CARD`, and `displayAffinity=0`.

Result: still not promoted (foreground stays on the input; no NL_VSC). One of the four
conditions isn't satisfied as expected — almost certainly either `displayAffinity` not
equal to the primary `displayId`, or the `set_property` values not landing on the item.
**Cannot confirm which:** the compositor's QML `console.log`/`console.warn` (incl. the
"request ignored" line and the item's type/displayAffinity) go to `/dev/null` (the
surface-manager process has fd1/fd2 → /dev/null; only structured PmLog `NL_VSC` lines are
logged). Reading `checkFullscreen`'s verdict needs restarting the compositor with its
output redirected — a full-UI restart, risky on the only TV.

### Two ways to finish (both viable)
1. **Debug the last detail:** restart `surface-manager` with stdout/stderr to a file (+
   QML logging), launch once, read `checkFullscreen`'s verdict, set the one wrong prop,
   done. Decisive but disruptive/risky.
2. **Pivot to LG's Qt runtime (recommended):** `/usr/bin/qml-runner` is on the TV. A QML
   app run through it uses the `QT_WAYLAND_SHELL_INTEGRATION=webos` plugin, which sets
   appId/type/displayAffinity/fullscreen correctly for free — the window would display
   without any of the hand-rolled set_property guesswork. Punch-through for the live video
   would still be driven via `wl_webos_foreign` (proven open) from the app. This sidesteps
   the entire compositor-integration gate.

Everything up to the gate is solved and reproducible: cross-compile → LS2 register →
registerApp "registered" → SAM "running" → surface commits. The overlay is one
compositor-integration detail (or a runtime pivot) from pixels on screen.

---

## BREAKTHROUGH (2026-11-07): overlay DISPLAYS — gate cracked via qml-runner

The last-mile compositor gate is solved. Pivoted off the hand-rolled native-C set_property path to
LG's Qt runtime: a webOS **`type:"qml"`** app, launched by SAM's `QmlAppLifeHandler` through
`/usr/bin/qml-runner`. Its `Eos.Window.WebOSWindow` QML type sets appId / windowType=CARD /
displayAffinity(int) / fullscreen correctly, and qml-runner does the full LS2 native lifecycle
(registerApp) itself under its own system identity — no custom role needed.

CONFIRMED on screen: `getForegroundAppInfo` returned `com.webosbrew.overlay`, and
`LSM NL_VSC {"app_id":"com.webosbrew.overlay","visible":true,"window_type":"_WEBOS_WINDOW_TYPE_CARD"}`
(hdmi3 went visible:false). App `com.webosbrew.overlay` v1.1.0 (type qml) is installed and dormant.

Full working recipe + build/deploy/launch commands + punch-through plan: **scratchpad/OVERLAY-RECIPE.md**.
Artifacts: scratchpad/overlayqml/{appinfo.json,main.qml,main-video.qml}, scratchpad/build_ipk_qml.py,
scratchpad/overlay-qml.ipk.

Punch-through for live HDMI: input group `com.webos.app.hdmi3` is `allowAnonymous:false` (can't join it).
Use `Eos.Items.PunchThrough` (QML, VT video API — ready in main-video.qml, needs 1 live launch to verify it
grabs the live feed) or, failing that, the proven `wl_webos_foreign` import_element+attach_punchthrough
from a native Qt app. Screen left on Shield, lock released.

---

## ✅ SOLVED — transparent overlay over LIVE HDMI confirmed on screen (user-verified 2026-11-07)

The full goal works. A homebrew `type:"qml"` app (`com.webosbrew.overlay` v1.1.1),
launched by SAM via `/usr/bin/qml-runner`, renders a `_WEBOS_WINDOW_TYPE_OVERLAY` window
on top of the live HDMI input and uses LG's `Eos.Items.PunchThrough` QML item to show the
**live Shield picture** behind translucent UI chrome. User confirmed live video visible
through the overlay; compositor logged `NL_VSC visible:true _WEBOS_WINDOW_TYPE_OVERLAY`
with `com.webos.app.hdmi3` staying foreground underneath. No rootfs/signed component touched.

Winning stack: `type:"qml"` app (qml-runner does the LS2 lifecycle + WebOSWindow sets
appId/windowType/displayAffinity/fullscreen for free) + `WebOSWindow{windowType:OVERLAY}`
+ `Eos.Items.PunchThrough{}` for the live video. Recipe: scratchpad/OVERLAY-RECIPE.md;
video QML: scratchpad/overlayqml/main-video.qml; builder: scratchpad/build_ipk_qml.py;
ipk: scratchpad/overlay-qml.ipk (v1.1.1). Route A2 (native Qt + wl_webos_foreign) is the
fallback and no longer needed.

NEXT: port the real input-selector UI (the HDMI/Shield tiles, current-input preselect,
back-to-live) into this QML overlay so the Input button opens an LG-style transparent
selector over the live picture — replacing the opaque web selector.
