# Shield Dolby Vision EDID fix (through a non-DV AVR)

An NVIDIA Shield plugged into a TV through an AV receiver that forwards a **corrupted**
Dolby Vision VSVDB block: the Shield parses the Dolby OUI but reads the capability bytes as
"supports nothing", so it falls back to HDR10. The fix is to feed the Shield an EDID that is
the AVR's EDID with a **valid** Dolby Vision block spliced in, via a programmable inline HDMI
EDID emulator.

> A software EDID override on the Shield's Tegra display driver (`/sys/kernel/debug/tegradc.0/edid`)
> works for reporting, but NVIDIA disables HDCP while a virtual EDID is active, so real playback
> black-screens. Use a hardware emulator presenting a real EDID instead.

The one changed CEA block (a 12-byte Dolby Vision VSVDB, CTA extended tag 0x01, OUI 00-D0-46):

```
was: eb 01 46 d0 00 48 23 7e 8c 3e 4e 8d   (corrupt: version 2, no usable caps)
now: eb 01 46 d0 00 26 18 03 91 82 69 7c   (valid v1: standard + low-latency DV, 2160p60)
```

Full 256-byte EDID to load onto the emulator (replace manufacturer/monitor-name bytes with your
own display's if you copy this verbatim — these identify a specific panel):

```
00 ff ff ff ff ff ff 00 4d d9 0c 05 01 01 01 01
32 1b 01 03 80 a0 5a 78 0a ee 91 a3 54 4c 99 26
0f 50 54 20 00 00 01 01 01 01 01 01 01 01 01 01
01 01 01 01 01 01 08 e8 00 30 f2 70 5a 80 b0 58
8a 00 40 84 63 00 00 1e 00 00 00 fe 00 0a 20 20
20 20 20 20 20 20 20 20 20 20 00 00 00 fc 00 4c
47 20 54 56 20 53 53 43 52 32 0a 20 00 00 00 fd
00 18 78 1e ff 77 00 0a 20 20 20 20 20 20 01 63
02 03 6c f0 57 61 60 66 65 10 1f 04 13 05 14 03
02 12 20 21 22 01 5d 5e 5f 62 63 64 38 0f 7f 07
15 07 50 3d 1f c0 57 06 01 67 7e 01 5f 7e 03 5f
7e 01 4d 02 00 83 5f 00 00 6e 03 0c 00 34 00 b8
3c 2c 00 80 01 02 03 04 67 d8 5d c4 01 78 80 03
e2 00 cf eb 01 46 d0 00 26 18 03 91 82 69 7c e3
05 c0 00 e4 0f 0f 00 00 e3 06 0d 01 00 00 00 00
00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 d3
```

Write it to a 256-byte file and load it with your emulator's tool, then wire
`Shield -> emulator -> AVR input`. The AVR passes the Dolby Vision signal the same way it
already passes HDR10, and HDCP authenticates normally because the emulator presents a real EDID.
