#!/usr/bin/env python3
"""
make_logo.py — turn any image into a flashable LG boot-logo partition image.

Produces a byte-exact match for the stock geometry on the 75NANO90UPA:
1920 x 450, 24-bit, bottom-up BMP, 2,592,056 bytes, wrapped in an LZ4P
container sized to fit /dev/mmcblk0p25 (512 KB).

The 54-byte BMP header is copied verbatim from the stock image rather than
synthesised, so MBoot sees exactly the structure it already parses.

Only `sips` (built into macOS) is used, and only for decoding/resizing the
source image to PNG. PNG parsing, BMP emission and LZ4P packing are all
done here with no third-party modules.

Usage:
    make_logo.py <input-image> <output.img> [options]

Options:
    --mode fit|cover|stretch   how to map the source onto 1920x450
                               fit     = contain, letterboxed      (default)
                               cover   = fill, centre-cropped
                               stretch = distort to exact size
    --bg RRGGBB                letterbox colour for --mode fit (default 1a1a1a,
                               sampled from the stock logo background)
    --preview out.png          also write a PNG of exactly what will be flashed
    --header-from <file.bmp>   stock BMP to copy the 54-byte header from
                               (default: tv-backup/logo_decompressed.bmp)
"""

import os
import struct
import subprocess
import sys
import tempfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lz4p  # noqa: E402

WIDTH, HEIGHT = 1920, 450
BPP = 3
TOTAL = 2_592_056          # exact stock file size
PART_SIZE = 0x80000        # 512 KB logo partition
STOCK_BMP = os.path.join(HERE, "tv-backup", "logo_decompressed.bmp")


# --------------------------------------------------------------------------
# minimal PNG decoder (8-bit, non-interlaced)
# --------------------------------------------------------------------------

def decode_png(path):
    """Return (width, height, rgb_rows) where each row is bytes of RGB triples."""
    raw = open(path, "rb").read()
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path}: not a PNG")

    pos = 8
    idat = bytearray()
    w = h = depth = ctype = interlace = None
    palette = None
    trns = None

    while pos < len(raw):
        ln, = struct.unpack_from(">I", raw, pos)
        typ = raw[pos + 4:pos + 8]
        body = raw[pos + 8:pos + 8 + ln]
        pos += 12 + ln
        if typ == b"IHDR":
            w, h, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", body)
        elif typ == b"PLTE":
            palette = body
        elif typ == b"tRNS":
            trns = body
        elif typ == b"IDAT":
            idat += body
        elif typ == b"IEND":
            break

    if depth != 8:
        raise ValueError(f"{path}: only 8-bit PNG supported (got {depth}-bit)")
    if interlace:
        raise ValueError(f"{path}: interlaced PNG not supported")

    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    data = zlib.decompress(bytes(idat))
    stride = w * channels

    rows = []
    prev = bytearray(stride)
    p = 0
    for _ in range(h):
        ft = data[p]
        p += 1
        line = bytearray(data[p:p + stride])
        p += stride
        if ft == 1:
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 0xFF
        elif ft == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ft == 3:
            for i in range(stride):
                a = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif ft == 4:
            for i in range(stride):
                a = line[i - channels] if i >= channels else 0
                b = prev[i]
                c = prev[i - channels] if i >= channels else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        elif ft != 0:
            raise ValueError(f"bad PNG filter type {ft}")
        rows.append(bytes(line))
        prev = line

    # normalise every colour type to RGB triples
    out = []
    for line in rows:
        if ctype == 2:
            out.append(line)
        elif ctype == 6:
            out.append(bytes(b for i in range(0, len(line), 4) for b in line[i:i + 3]))
        elif ctype == 0:
            out.append(bytes(b for v in line for b in (v, v, v)))
        elif ctype == 4:
            out.append(bytes(b for i in range(0, len(line), 2)
                             for b in (line[i], line[i], line[i])))
        elif ctype == 3:
            out.append(bytes(b for v in line for b in palette[v * 3:v * 3 + 3]))
        else:
            raise ValueError(f"unsupported PNG colour type {ctype}")
    return w, h, out


# --------------------------------------------------------------------------
# sips helpers
# --------------------------------------------------------------------------

def sips_dims(path):
    r = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", path],
                       capture_output=True, text=True, check=True)
    w = h = None
    for line in r.stdout.splitlines():
        line = line.strip()
        if line.startswith("pixelWidth:"):
            w = int(line.split(":")[1])
        elif line.startswith("pixelHeight:"):
            h = int(line.split(":")[1])
    if not w or not h:
        raise RuntimeError(f"could not read dimensions of {path}")
    return w, h


def render_source(src, mode, bg, tmp):
    """Resize `src` onto exactly WIDTH x HEIGHT, returning a PNG path."""
    sw, sh = sips_dims(src)
    staged = os.path.join(tmp, "staged.png")
    subprocess.run(["sips", "-s", "format", "png", src, "--out", staged],
                   capture_output=True, check=True)

    if mode == "stretch":
        subprocess.run(["sips", "--resampleHeightWidth", str(HEIGHT), str(WIDTH),
                        staged, "--out", staged], capture_output=True, check=True)
        return staged

    if mode == "fit":
        scale = min(WIDTH / sw, HEIGHT / sh)
    else:  # cover
        scale = max(WIDTH / sw, HEIGHT / sh)
    nw, nh = max(1, round(sw * scale)), max(1, round(sh * scale))

    subprocess.run(["sips", "--resampleHeightWidth", str(nh), str(nw),
                    staged, "--out", staged], capture_output=True, check=True)

    if mode == "fit":
        subprocess.run(["sips", "--padToHeightWidth", str(HEIGHT), str(WIDTH),
                        "--padColor", bg, staged, "--out", staged],
                       capture_output=True, check=True)
    else:
        subprocess.run(["sips", "-c", str(HEIGHT), str(WIDTH), staged, "--out", staged],
                       capture_output=True, check=True)
    return staged


# --------------------------------------------------------------------------
# BMP emission
# --------------------------------------------------------------------------

def build_bmp(rgb_rows, header):
    """Bottom-up 24-bit BGR BMP using the stock 54-byte header verbatim."""
    body = bytearray()
    for row in reversed(rgb_rows):                 # BMP stores bottom row first
        body += bytes(row[i + 2 - j] for i in range(0, WIDTH * 3, 3) for j in range(3))
    out = bytearray(header)
    out += body
    if len(out) < TOTAL:
        out += b"\x00" * (TOTAL - len(out))
    return bytes(out[:TOTAL])


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    src, dst = argv[1], argv[2]

    def opt(name, default=None):
        return argv[argv.index(name) + 1] if name in argv else default

    mode = opt("--mode", "fit")
    bg = opt("--bg", "1a1a1a")
    preview = opt("--preview")
    stock = opt("--header-from", STOCK_BMP)

    if mode not in ("fit", "cover", "stretch"):
        print(f"bad --mode {mode!r}", file=sys.stderr)
        return 2
    if not os.path.exists(stock):
        print(f"ERROR: stock BMP not found: {stock}\n"
              f"       (needed for the verbatim 54-byte header)", file=sys.stderr)
        return 1

    header = open(stock, "rb").read(54)
    w, h = struct.unpack_from("<ii", header, 18)
    if (w, h) != (WIDTH, HEIGHT):
        print(f"ERROR: stock header is {w}x{h}, expected {WIDTH}x{HEIGHT}", file=sys.stderr)
        return 1

    tmp = tempfile.mkdtemp()
    print(f"source      {src}  ({'x'.join(map(str, sips_dims(src)))})")
    print(f"mode        {mode}" + (f"  bg #{bg}" if mode == "fit" else ""))

    png = render_source(src, mode, bg, tmp)
    pw, ph, rows = decode_png(png)
    if (pw, ph) != (WIDTH, HEIGHT):
        print(f"ERROR: rendered {pw}x{ph}, expected {WIDTH}x{HEIGHT}", file=sys.stderr)
        return 1

    bmp = build_bmp(rows, header)
    if len(bmp) != TOTAL:
        print(f"ERROR: BMP is {len(bmp)} bytes, stock is {TOTAL}", file=sys.stderr)
        return 1
    print(f"bitmap      {WIDTH}x{HEIGHT} 24bpp, {len(bmp):,} bytes (matches stock)")

    blob = lz4p.pack(bmp)
    pct = 100.0 * len(blob) / PART_SIZE
    print(f"packed      {len(blob):,} bytes  ({pct:.1f}% of the {PART_SIZE:,}-byte partition)")

    if len(blob) > PART_SIZE:
        print(f"\nERROR: too big for the partition. Try flatter artwork — large areas of\n"
              f"       solid colour compress far better than photographs or gradients.",
              file=sys.stderr)
        return 1

    # prove it before it ever reaches the TV
    if lz4p.unpack(blob) != bmp:
        print("ERROR: round-trip verification FAILED, refusing to write", file=sys.stderr)
        return 1
    print("verify      round-trip OK (unpack(pack(x)) == x)")

    open(dst, "wb").write(blob)
    print(f"wrote       {dst}")

    if preview:
        tmp_bmp = os.path.join(tmp, "preview.bmp")
        open(tmp_bmp, "wb").write(bmp)
        subprocess.run(["sips", "-s", "format", "png", tmp_bmp, "--out", preview],
                       capture_output=True, check=True)
        print(f"preview     {preview}")

    print(f"\nFlash with (after staging the restore of tv-backup/p25.img):")
    print(f"    scp {os.path.basename(dst)} root@192.0.2.6:/tmp/")
    print(f"    ssh root@192.0.2.6 "
          f"'dd if=/tmp/{os.path.basename(dst)} of=/dev/mmcblk0p25 bs=512 conv=fsync'")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
