#!/usr/bin/env python3
"""
lz4p.py — pack/unpack the MStar "LZ4P" container used by the LG webOS
boot-logo partition (`logo` / logo.img, /dev/mmcblk0p25 on 75NANO90UPA).

Container layout (all little-endian), derived from the stock image:

    0x00  char[4]  "LZ4P"
    0x04  u32      uncompressed total size
    0x08  u32      total container size (header + table + data)
    0x0c  u32      block size (0x40000 = 262144)
    0x10  u32      block count
    0x14  u32      version (1)
    0x18  u32      0
    0x1c  u32      0
    0x20  u32[n]   compressed size of each block
    0x20+4n        raw LZ4 blocks, concatenated

Each block is a bare LZ4 block (no frame header, no checksum) that
decompresses to exactly `block size` bytes, except the last.

No third-party modules required.

Usage:
    lz4p.py unpack <logo.img> <out.bmp>
    lz4p.py pack   <in.bmp> <out.img> [--part-size 524288]
    lz4p.py test   <logo.img>        # round-trip proof against the stock image
    lz4p.py info   <logo.img>
"""

import os
import struct
import sys

MAGIC = b"LZ4P"
HDR = 0x20
DEFAULT_BLOCK = 0x40000
PART_SIZE = 0x80000  # 512 KB logo partition

# LZ4 block-format constants
MINMATCH = 4
MFLIMIT = 12
LASTLITERALS = 5
MAX_OFFSET = 65535


# --------------------------------------------------------------------------
# LZ4 raw block codec
# --------------------------------------------------------------------------

def lz4_decompress_block(src: bytes, expected: int) -> bytes:
    """Decode one bare LZ4 block. `expected` is the known output size."""
    out = bytearray()
    i, n = 0, len(src)
    while i < n:
        token = src[i]
        i += 1

        lit = token >> 4
        if lit == 15:
            while True:
                b = src[i]
                i += 1
                lit += b
                if b != 255:
                    break
        out += src[i:i + lit]
        i += lit

        if i >= n:
            break  # last sequence is literals only

        offset = src[i] | (src[i + 1] << 8)
        i += 2
        if offset == 0:
            raise ValueError("invalid LZ4 stream: zero offset")

        mlen = token & 15
        if mlen == 15:
            while True:
                b = src[i]
                i += 1
                mlen += b
                if b != 255:
                    break
        mlen += MINMATCH

        start = len(out) - offset
        if start < 0:
            raise ValueError("invalid LZ4 stream: offset before start of output")
        # byte-wise on purpose: overlapping matches are legal and common
        for k in range(mlen):
            out.append(out[start + k])

    if expected is not None and len(out) != expected:
        raise ValueError(f"block decoded to {len(out)} bytes, expected {expected}")
    return bytes(out)


def _emit(out: bytearray, src: bytes, anchor: int, ip: int, mlen: int, offset: int):
    """Emit one LZ4 sequence: literals, then (optionally) a match."""
    lit = ip - anchor
    token_lit = 15 if lit >= 15 else lit

    if mlen is None:
        out.append(token_lit << 4)
        if lit >= 15:
            rem = lit - 15
            while rem >= 255:
                out.append(255)
                rem -= 255
            out.append(rem)
        out += src[anchor:ip]
        return

    m = mlen - MINMATCH
    token_match = 15 if m >= 15 else m
    out.append((token_lit << 4) | token_match)

    if lit >= 15:
        rem = lit - 15
        while rem >= 255:
            out.append(255)
            rem -= 255
        out.append(rem)
    out += src[anchor:ip]

    out.append(offset & 0xFF)
    out.append((offset >> 8) & 0xFF)

    if m >= 15:
        rem = m - 15
        while rem >= 255:
            out.append(255)
            rem -= 255
        out.append(rem)


def lz4_compress_block(src: bytes) -> bytes:
    """
    Greedy LZ4 block compressor with a 4-byte hash table.

    Honours the two format rules that decoders rely on:
      * the last LASTLITERALS (5) bytes are always emitted as literals
      * no match may start within MFLIMIT (12) bytes of the end
    """
    n = len(src)
    out = bytearray()
    if n < MFLIMIT + 1:
        _emit(out, src, 0, n, None, 0)
        return bytes(out)

    mflimit = n - MFLIMIT
    matchlimit = n - LASTLITERALS
    table = {}
    anchor = 0
    ip = 0

    while ip < mflimit:
        seq = src[ip:ip + 4]
        ref = table.get(seq, -1)
        table[seq] = ip

        if ref < 0 or ip - ref > MAX_OFFSET:
            ip += 1
            continue

        # extend the match backwards over already-pending literals
        while ip > anchor and ref > 0 and src[ip - 1] == src[ref - 1]:
            ip -= 1
            ref -= 1

        # extend forwards, stopping short of the mandatory trailing literals
        mlen = MINMATCH
        while ip + mlen < matchlimit and src[ip + mlen] == src[ref + mlen]:
            mlen += 1

        _emit(out, src, anchor, ip, mlen, ip - ref)

        # index the interior of the match so later sequences can find it
        for k in range(ip + 1, min(ip + mlen, mflimit)):
            table[src[k:k + 4]] = k

        ip += mlen
        anchor = ip

    _emit(out, src, anchor, n, None, 0)
    return bytes(out)


# --------------------------------------------------------------------------
# LZ4P container
# --------------------------------------------------------------------------

def unpack(blob: bytes) -> bytes:
    if blob[:4] != MAGIC:
        raise ValueError(f"not an LZ4P container (magic = {blob[:4]!r})")
    unc, total, bsize, nblk, ver = struct.unpack_from("<IIIII", blob, 4)
    sizes = list(struct.unpack_from(f"<{nblk}I", blob, HDR))
    off = HDR + 4 * nblk

    out = bytearray()
    for k, csz in enumerate(sizes):
        want = min(bsize, unc - len(out))
        out += lz4_decompress_block(blob[off:off + csz], want)
        off += csz

    if len(out) != unc:
        raise ValueError(f"decoded {len(out)} bytes, header says {unc}")
    return bytes(out)


def pack(data: bytes, block_size: int = DEFAULT_BLOCK, version: int = 1) -> bytes:
    nblk = (len(data) + block_size - 1) // block_size
    blocks = [
        lz4_compress_block(data[i * block_size:(i + 1) * block_size])
        for i in range(nblk)
    ]
    total = HDR + 4 * nblk + sum(len(b) for b in blocks)

    out = bytearray()
    out += MAGIC
    out += struct.pack("<IIIII", len(data), total, block_size, nblk, version)
    out += struct.pack("<II", 0, 0)
    for b in blocks:
        out += struct.pack("<I", len(b))
    for b in blocks:
        out += b
    assert len(out) == total, (len(out), total)
    return bytes(out)


def info(blob: bytes) -> str:
    unc, total, bsize, nblk, ver = struct.unpack_from("<IIIII", blob, 4)
    sizes = list(struct.unpack_from(f"<{nblk}I", blob, HDR))
    lines = [
        f"magic            {blob[:4].decode()}",
        f"uncompressed     {unc:,} bytes",
        f"container size   {total:,} bytes",
        f"block size       {bsize:,} ({bsize:#x})",
        f"block count      {nblk}",
        f"version          {ver}",
        f"block sizes      {sizes}",
        f"sum(blocks)      {sum(sizes):,}",
        f"data offset      {HDR + 4 * nblk:#x}",
    ]
    return "\n".join("  " + x for x in lines)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _round_trip_test(path: str) -> int:
    stock = open(path, "rb").read()
    print(f"stock container: {os.path.basename(path)}")
    print(info(stock))

    print("\n[1] unpacking stock image ...")
    payload = unpack(stock)
    print(f"    -> {len(payload):,} bytes")

    print("[2] re-packing that payload with our compressor ...")
    rebuilt = pack(payload)
    print(f"    -> {len(rebuilt):,} bytes container")

    print("[3] unpacking our container again ...")
    payload2 = unpack(rebuilt)
    print(f"    -> {len(payload2):,} bytes")

    ok_payload = payload == payload2
    print(f"\n    payload round-trip byte-identical : {'PASS' if ok_payload else 'FAIL'}")

    unc_s, total_s, bs_s, nb_s, ver_s = struct.unpack_from("<IIIII", stock, 4)
    unc_r, total_r, bs_r, nb_r, ver_r = struct.unpack_from("<IIIII", rebuilt, 4)
    ok_hdr = (unc_s, bs_s, nb_s, ver_s) == (unc_r, bs_r, nb_r, ver_r)
    print(f"    header fields match stock         : {'PASS' if ok_hdr else 'FAIL'}")

    ok_fit = len(rebuilt) <= PART_SIZE
    pct = 100.0 * len(rebuilt) / PART_SIZE
    print(f"    fits {PART_SIZE:,}-byte partition     : "
          f"{'PASS' if ok_fit else 'FAIL'}  ({len(rebuilt):,} B, {pct:.1f}% full)")

    print(f"\n    stock container    {100.0 * total_s / len(payload):5.2f}% of payload "
          f"({total_s:,} B)")
    print(f"    ours               {100.0 * total_r / len(payload):5.2f}% of payload "
          f"({total_r:,} B)   [{total_r / total_s:.2f}x larger, irrelevant at this size]")

    return 0 if (ok_payload and ok_hdr and ok_fit) else 1


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd = argv[1]

    if cmd == "unpack" and len(argv) >= 4:
        open(argv[3], "wb").write(unpack(open(argv[2], "rb").read()))
        print(f"wrote {argv[3]} ({os.path.getsize(argv[3]):,} bytes)")
        return 0

    if cmd == "pack" and len(argv) >= 4:
        limit = PART_SIZE
        if "--part-size" in argv:
            limit = int(argv[argv.index("--part-size") + 1])
        blob = pack(open(argv[2], "rb").read())
        if len(blob) > limit:
            print(f"ERROR: {len(blob):,} bytes exceeds the {limit:,}-byte partition",
                  file=sys.stderr)
            return 1
        open(argv[3], "wb").write(blob)
        print(f"wrote {argv[3]} ({len(blob):,} bytes, "
              f"{100.0 * len(blob) / limit:.1f}% of partition)")
        return 0

    if cmd == "info" and len(argv) >= 3:
        print(info(open(argv[2], "rb").read()))
        return 0

    if cmd == "test" and len(argv) >= 3:
        return _round_trip_test(argv[2])

    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
