# LG 75NANO90UPA — boot logo replacement: recovery notes

## The TV

| | |
|---|---|
| Model | 75NANO90UPA (2021 NanoCell) |
| Serial | 106RMUY10070 |
| webOS | 6.5.3-47 "Rockhopper" (kernel 4.4.84-899.19.koli.1, armv7l) |
| SoC | `chip=LM21UA0` — MStar/MediaTek, platform `h13_emmc` |
| Bootloader | MBoot, `bver=0.1.181`, preceded by `sboot` (ROM stage) |
| eMMC | 7.28 GiB (`emmc_size=0x1d1fff000`), 53 partitions |
| IP / MAC | 192.0.2.6 (Ethernet) — `DE:AD:BE:EF:CA:FE` |
| Root | webosbrew / Homebrew Channel, `/var/lib/webosbrew/`, SSH as root on :22 |
| Serial console | `console=ttyS0,115200`, `debugMode=5` |
| Secure boot | `SECURITY=ON`, `tee_mode=optee` |

## Where the logo actually is

`/dev/mmcblk0p25` — partition `logo`, file `logo.img`, offset `0x07d00000`, size `0x80000` (512 KB).

Contents: an **`LZ4P` container** (MStar chunked LZ4) — 10 blocks of 256 KB, 42,868 bytes
compressed → 2,592,056 bytes, which decompresses to a **1920 × 450, 24-bit uncompressed
BMP**. Decoded copy: `tv-backup/logo_decompressed.bmp`, rendered as `current-logo.png`.

Only ~42 KB of the 512 KB partition is used, so a replacement has roughly 12× headroom
before it has to compress as well as the original.

Despite the `BOOTLOGO_IN_MBOOT` kernel argument, the logo bytes are **not** inside the MBoot
binary — that flag selects which code path MBoot uses. The logo is its own partition.

### Why that matters

MBoot's signature list (`do_save_secure_info`) covers: `keySet`, `kernel`, `ROOTFS`,
`mslib`, `config`, `applications`, `tee`. **The logo is not in it.** `CRC32.INFO`
(`/dev/mmcblk0p9`) contains only ~104 bytes — a UUID and what look like three SHA-256
digests — and none of them match any CRC32 of p25. So the logo is not in the signed chain.

There is a `logo_crc` reference in MBoot, and `db_table.logo_offset` / `db_table.logo_size`,
which live in `dbboot` (`/dev/mmcblk0p44`). That partition is encrypted (16-byte plaintext
header, magic `0x485DD542`, then high-entropy data, zero strings), so whether `logo_crc` is
enforced could not be determined statically. **Assume it is.**

### The likely failure mode is mild

MBoot's logo error paths all print and continue:
`get logo_size fail...`, `ERROR: Read_LogoToDisplayAddr fail...`, `check LogoToDisplayAddr fail...`,
`no bootlogo show for webos 6.0`, `[DISP] OLED display - Bypassing bootlogo display`,
`destroy_logo - Stop logo display`.

By contrast, the *verification* failures say `System will stop` explicitly. The logo code has
no such path. The expected outcome of a bad logo is **no logo at boot**, not a brick.

## Recovery assets that exist on this platform

Found as command strings inside MBoot (`p2.img`), i.e. available from the serial console:

- **`backup [on/off]`** — "set backup partition booting mode". The platform is A/B: `boot`,
  `kernel`, `sedata`, `rootfs`, `bsppart`, `otncabi`, `otycabi`, `fonts`, `tzfw`, `license`,
  `intmicom`, `pmsfw`, `swue` all exist twice. **`logo` does not** — there is exactly one copy.
- **`bootlogo 0 0 1 1 boot0.jpg`** and **`testlogo`** ("boot logo test") — MBoot can render a
  logo read from **USB** (`%s/boot0.jpg`). This is a test path that writes nothing to flash.
- **`mboot upgrade`** / `do_mboot_upgrade` / `/MbootUpgrade.bin` / `has mboot upgrade bin` —
  sanctioned bootloader reflash from USB.
- `fullverify [on/off]`, `sb_verify`, `do_sb_verify`, `dumpSignature`, `store_secure_info`.
- `MBOOT PARTITION ERROR REPAIR: Remove partition %s success!`

MBoot A (`p2`) and MBoot B (`p3`) are **byte-identical** (md5 `1d18c3de…`).

## Recovery tiers, in order

1. **SSH still works** → `dd` `tv-backup/p25.img` back. Costs nothing. Protect this above all.
2. **UART serial console, 3.3V, 115200 8N1 on ttyS0.** Gets the MBoot prompt, where
   `backup on` and `mboot upgrade` live. **Set this up and confirm you get a prompt before
   writing anything.** This is the single highest-value piece of insurance here, and unlike
   the usual webOS advice it needs no prior debug enable — the console is already configured
   in the kernel cmdline.
3. **USB firmware recovery** — stock `.epk` for 75NANO90UPA in a folder named `LG_DTV`,
   FAT32, must be the **USB** build not the NSU build. Download it before you start.
4. **eMMC ISP clip** + the dumps in `tv-backup/`.
5. Mainboard replacement / LG service.

## What is backed up here

`tv-backup/` — 181 MB, 42 images, `MD5SUMS.txt` alongside. Every boot- and security-critical
partition, verified by md5 at both ends:

`secureboot`(p1) `boot`A/B(p2,p3) `partinfo`(p4) `mapbak`(p5) `swue`A/B(p6,p7)
`emergency`(p8) `crc32info`(p9) `macadr`(p10) `env_nvm`(p11) `widevine`(p12) `idfile`(p13)
`cert`(p14) `authcxt`(p15) `nvram`(p16) `marlin`(p17) `xcas`(p18) `sestore`(p19)
`wossestore`(p20) `kernel`A/B(p21,p22) `sedata`A/B(p23,p24) **`logo`(p25)** `pmsfw`(p26,p35)
`otycabi`(p30,p39) `tzfw`(p32,p41) `license`(p33,p42) `intmicom`(p34,p43) `dbboot`(p44)
`uhdcp`(p45) `profdata`(p46) `dump`(p49) `hist`(p50) plus eMMC `boot0`/`boot1`.

**Not** backed up (large, and restorable from an LG `.epk`): `rootfs` (p27/p36, 1.4 GB each),
`bsppart`, `otncabi`, `fonts`, `efs`, `hib`, `db8`, `data`, `apps`.

`macadr` (p10) and `nvram` (p16) hold the MAC and per-set calibration — those are **not** in
any firmware image and cannot be re-downloaded. They are in `tv-backup/`. Keep them.

## Full partition map

Decoded from `PART.INFO` (`p4.img`), record stride `0x60`, name at `+0x00`, u64 offset at
`+0x20`, u64 size at `+0x28`. Every offset/size cross-checks against `/proc/partitions`.

| node | name | offset | size |
|---|---|---|---|
| p1 | secureboot | 0x00000000 | 2 MB |
| p2 | boot (MBoot A) | 0x00200000 | 4 MB |
| p3 | boot (MBoot B) | 0x00600000 | 4 MB |
| p4 | partinfo | 0x00a00000 | 256 KB |
| p5 | mapbak | 0x00a40000 | 256 KB |
| p6/p7 | swue A/B | 0x00a80000 | 20 MB |
| p8 | emergency | 0x03280000 | 256 KB |
| p9 | crc32info | 0x032c0000 | 256 KB |
| p10 | macadr | 0x03300000 | 256 KB |
| p11 | env_nvm | 0x03340000 | 256 KB |
| p15 | authcxt | 0x03500000 | 6 MB |
| p16 | nvram | 0x03b00000 | 8 MB |
| p21/p22 | kernel A/B | 0x04c00000 | 24 MB |
| p23/p24 | sedata A/B | 0x07c00000 | 512 KB |
| **p25** | **logo** | **0x07d00000** | **512 KB** |
| p27/p36 | rootfs A/B | 0x07e80000 | 1.37 GB |
| p44 | dbboot | 0xd3a00000 | 4 MB |
| p47 | efs | 0xd4380000 | 600 MB |
| p48 | hib (resume) | 0xf9b80000 | 150 MB |
| p51 | db8 | 0x103c00000 | 112 MB |
| p52 | data | 0x10ac00000 | 750 MB |
| p53 | apps | 0x139a00000 | 2.38 GB |

Active slot is A: `root=/dev/mmcblk0p27`, `resume=/dev/mmcblk0p48`.

## Tooling (built and verified)

`lz4p.py` — packs/unpacks the MStar `LZ4P` container. Pure Python, no dependencies.

```
python3 lz4p.py test   tv-backup/p25.img      # round-trip proof
python3 lz4p.py unpack tv-backup/p25.img out.bmp
python3 lz4p.py pack   in.bmp out.img
```

`make_logo.py` — turns any image into a flashable partition image matching the stock
geometry exactly. Uses `sips` (built into macOS) only to decode/resize the source; PNG
parsing, BMP emission and packing are all local.

```
python3 make_logo.py art.png newlogo.img --mode fit --bg 1a1a1a --preview out.png
```

Modes: `fit` (contain + letterbox, default), `cover` (fill + centre-crop), `stretch`.
It refuses to write anything larger than the 512 KB partition and self-verifies
`unpack(pack(x)) == x` before writing.

### What has been proven

| Check | Result |
|---|---|
| Our unpacker vs stock image | 2,592,056 bytes out, exact header match |
| Our decoder vs reference `lz4` v1.10.0 on LG's own blocks | all 10 blocks MATCH |
| Our compressor's blocks decoded by reference `lz4` | all 10 blocks MATCH |
| `unpack(pack(payload)) == payload` | byte-identical |
| Full pipeline: stock PNG → BMP → pack → unpack | **byte-identical to stock bitmap** |
| Size | 57,665 B = 11.0% of the partition |

Our compressor is ~1.35× weaker than LG's (57,665 vs 42,868 bytes). At 11% occupancy that
is irrelevant — there is room for roughly 9× more entropy before it starts to matter.

### What has NOT been proven

**That the TV accepts our container.** Everything above is verified on the Mac against a
reference LZ4 implementation. The header fields match stock exactly and the payload is
byte-identical, but the compressed bytes necessarily differ, and whether `logo_crc` in the
encrypted `dbboot` is enforced remains unknown.

## Replacement procedure

1. Get UART up and confirm an MBoot prompt. Do not skip this.
2. **Flash the rebuilt-but-unmodified image first.** `make_logo.py current-logo.png` yields a
   container whose payload is byte-identical to stock but whose compressed bytes are ours.
   If the TV boots and shows the normal logo, the format is accepted and `logo_crc` is not a
   blocker. That one test separates "is our container valid?" from "is our art good?".
3. Only then build and flash real art.
4. Keep `tv-backup/p25.img` on the Mac with the restore staged in a second open SSH session.

```
dd if=p25.img of=/dev/mmcblk0p25 bs=512 conv=fsync
```

### Open questions

- Is `logo_crc` in `dbboot` actually enforced? Unresolved — `dbboot` is encrypted. Step 2
  above answers this empirically.
- Does `testlogo` / `bootlogo … boot0.jpg` read from USB on this build? Strings say yes;
  untested. If it works, it is a zero-risk way to preview art before any flash write.

---

## Status log

**2026-11-06** — Wrote our rebuilt container to `/dev/mmcblk0p25` (payload byte-identical
to stock, compressed bytes ours), verified by readback, then **restored stock before any
reboot**. The TV never booted from the modified partition, so the format question remains
open and untested on hardware. p25 is byte-identical to the original dump; verified by md5
on the device and by full byte comparison after pulling it back.

A stock restore copy remains on the TV at `/mnt/lg/user/logo-restore/p25-stock.img`
(persistent across reboots).

### Static analysis attempt — did not succeed

Tried to settle "does a bad logo halt or skip?" by disassembling MBoot. Could not locate the
logo-handling code. The logo strings in `p2` have **no references from p2's ARM code** under
any addressing mode tested: literal pools (at any base), `ADR` (92 instructions, 0 hits), or
`MOVW`/`MOVT`. The image is not compressed (entropy 5.4–6.4, plain ARM) but it is a
**multi-segment container** with separate code blobs around `0x230000` and `0x2a0000`. For a
multi-segment image, a string pointer is `vaddr(segment) + (file_off − file_off(segment))`,
so no single global load base can resolve these references — which is why every base-recovery
attempt failed.

**Use Ghidra** for this. It handles segment detection, xrefs and ARM decompilation properly.

### Next time, in order

1. UART first — 3.3V, 115200 8N1 on ttyS0. Gets the MBoot console.
2. Try `testlogo` / `bootlogo 0 0 1 1 boot0.jpg` to render from USB with **no flash write**.
3. Only then flash, starting with the rebuilt-unmodified image as the format test.

---

## Ghidra analysis — the logo path cannot halt the boot

Ghidra 12.2 headless (needs **JDK 25**; the mac_arm_64 decompiler is absent from the public
release and must be built from `Ghidra/Features/Decompiler/src/decompile/cpp` with
`make ghidra_opt ARCH_TYPE="-arch arm64"`, since the Makefile hardcodes x86_64).

Import: raw `ARM:LE:32:v7`, `BinaryLoader`, **base `0x1F000000`** — confirmed correct:
3,259 functions, 323,689 instructions, 4,805 of 8,741 strings referenced.

**Why every hand-rolled xref attempt failed:** MBoot is **position-independent**. Addresses
are formed as `ldr rN,[pc,#x]; add rN,pc,rN` — the literal pool holds PC-relative
*displacements*, not absolute pointers. Searching for absolute pointers at any base was
never going to work.

### `FUN_1f0886a0` — bootlogo init

```c
void FUN_1f0886a0(void)
{
  printf("Bootlogo Initializing...\n");
  printf("no bootlogo show for webos 6.0\n");      // UNCONDITIONAL
  printf("Creating thread=%s, pri=%d, cpu= %d\n", "logo", 0xff, 2);
  iVar2 = thread_create("logo", entry, 0, 0, 2, 0xff, 1);
  *handle = iVar2;
  if (iVar2 == 0) { printf("logo thread create fail...\n"); return; }
  return;
}
```

Every path returns. The only error handling is a `printf`. No halt, no loop, no status
returned to the caller.

Its **sole caller** is `FUN_1f078d2c @ 1f078d2c`, which invokes it as a bare `FUN_1f0886a0();`
— void, result ignored, execution continues straight to the next init step.

### Supporting evidence

| Check | Result |
|---|---|
| `"no bootlogo show for webos 6.0"` | printed unconditionally, no flag test |
| `ERROR: Read_LogoToDisplayAddr fail...` | **0 references** |
| `check LogoToDisplayAddr fail...` | **0 references** |
| `logo_crc` | **0 references** |
| `db_table.logo_size=0x%x` | **0 references** |
| logo partition offset `0x7d00000` as immediate | 0 occurrences |

**Verdict: nothing in the boot-logo path can stop the boot.** A malformed logo cannot brick
this TV via MBoot's logo code, because that code has no failure path other than printing.

### What is still NOT established

- The spawned thread is named `logo`, but its entry point lives in a **GOT slot filled at
  runtime** (static value `0x2356cf18`, outside the image). Whatever reads or validates p25
  would be there, and it was not traced. **This is the real remaining gap.**
- `refs=0` is suggestive, not conclusive: 45% of all strings show no references, so some PIC
  references are certainly unresolved.
- `0x7d00000` not appearing as an immediate proves nothing — partition offsets come from
  `PART.INFO` at runtime.

Scripts and full output: `ghidra/`.

---

## Full verification / halt sweep of MBoot

Method: Ghidra at base `0x1F000000`, enumerate every `b .` spin loop, every security-related
string with a cross-reference, and the call graph between them. Scripts in `ghidra/`.

### Call-graph reliability (checked before drawing conclusions)

3,259 functions; **294 (9.0%)** have zero incoming references, and `printf` resolves with
**6,562** references. The call graph is sound, so `refs=0` on a specific function is
meaningful evidence rather than an analysis artifact.

### There is exactly one halt primitive, with exactly one caller

```c
void Secure_HaltCPU(void) {            // FUN_1f039e5c
  if (dbg & 1) printf("Secure_HaltCPU while loop", ...);
  while (true) { }                      // hard stop
}
```

| | |
|---|---|
| Callers of `Secure_HaltCPU` | **1** — `_RawData_Authentication` @`1f03d3e0` |
| Callers of `_RawData_Authentication` | **0** |

`_RawData_Authentication` halts on a failed size check, or after **3** failed
`Secure_doAuthentication` retries. But nothing calls it by direct branch in this build.

### Spin loops are not verification failures

95 `b .` spin loops exist in MBoot. Only 8 functions contain both a spin loop and a
security-related string, and **7 of those are `eMMC_IPVerify_*`** — eMMC *hardware signal
integrity* tests (factory diagnostics: `[eMMC IPVerify Fail: %Xh]`), not image verification.
The eighth is `Secure_HaltCPU` itself.

### Signature-verification functions do not halt

None of these contain a spin loop; all return status codes to their caller:

| Function | refs |
|---|---|
| `_sb_verify_image` @1f03f8dc | 1 |
| `_sb_partial_verification` @1f03ff8c | 0 |
| `_sb_real_full_verification_with_sha_accumulation` @1f040440 | 0 |
| `Secure_verifySignature` @1f046cdc | 2 |
| `Secure_doAuthentication` @1f046e9c | 2 |
| `snapshot_image_verify` @1f046ff0 | 1 |
| `verify_snapshot_image` @1f08b4ac | 1 |
| `lg_sb_verify_image` @1f2a0de4 | 2 |

The per-image signature slot strings — `kernelSign`, `ROOTFSSign`, `mslibSign`, `configSign`,
`applicationsSign`, `teeSign`, `keySetSign`, `keySet` — **all have refs=0**. So do
`sb verify fail`, `Load signature fail`, `Check signature fail`, `verify tee fail`,
`do_SecureKLBoot fail`.

### Verdict

**In MBoot as shipped on this TV, no reachable code path halts the CPU on a verification
failure.** The single halt primitive is reached only through a function nothing calls.

### Limits of this result — read before relying on it

- **Indirect calls are not covered.** The binary is PIC with a runtime-filled GOT. A call
  through a function pointer would not appear in the call graph, so "0 callers" means no
  *direct* branch, not provably dead.
- **This is MBoot only.** The mask-ROM / `sboot` stage that verifies MBoot itself lives in
  ROM, not in flash (`p1` is 2 MB with ~4 KB non-zero and zero spin instructions), so it
  cannot be analysed from these dumps. That stage is the one real enforcement point, and it
  protects `boot` (p2/p3) — which is exactly why p2/p3 should never be written.
- **The kernel was not analysed.** `p21`/`p22` contain 76 spin loops of their own, which are
  ordinary panic/idle paths, not partition verification.
- Nothing here was tested on hardware.

### Practical reading

| Image | Partition | In MBoot's signing list | Reachable halt on failure |
|---|---|---|---|
| MBoot | p2 / p3 | verified by ROM stage (not analysable here) | assume yes — do not write |
| kernel | p21 / p22 | slot string present, refs=0 | none found |
| rootfs | p27 / p36 | slot string present, refs=0 | none found |
| snapshot | p48 | `verify_snapshot_image` refs=1 | returns status, no halt |
| **logo** | **p25** | **absent from signing list** | **none — init prints and returns** |

---

## The boot "BIOS" chain — where the enforcing checks actually are

A TV has no PC-style BIOS/UEFI. The equivalent is the boot-firmware chain. Verification is
concentrated at the **front** of the chain, not in MBoot:

```
  [SoC mask ROM]  -> verifies ->  [sboot]  -> authenticates ->  [MBoot]  -> loads ->  [kernel]
   (in silicon)                   (boot0)                       (p2/p3)              (p21/p22)
   ROOT OF TRUST                  ENFORCING                     checks, no            no runtime
   not in flash                   halts on fail                 reachable halt        integrity
```

### Stage 0 — SoC mask ROM (in silicon, not in flash)
`IsBootingFromMaskRom`, `eMMC Rom boot verify pass!!`, `eMMC Rom boot checksum:%xh mismatch`.
The mask ROM is the hardware root of trust. It loads the first-stage bootloader from the eMMC
**boot partition** (`mmcblk0boot0`) and verifies it. Cannot be read or changed from flash.

### Stage 1 — sboot (the real "BIOS"), in `boot0` / `mmcblk0boot0`
This is the enforcing secure bootloader. `boot0.img` (dumped): **version 0.01.179** (matches
`sver=0.01.179` in the kernel cmdline), ~32 KB of Thumb-2 code, built GCC Sourcery 2011.03.

- **Starts with a 646-byte signature block** (high-entropy, offset 0x0) — this is what the
  mask ROM verifies.
- **Authenticates OP-TEE and MBoot**: MBoot's own log string says
  `tzfw(OPTEE) has been Authenticated in sboot`.
- Crypto key material: `MStarCommonTAKey`, `MStarHmacKey`.
- `AuthenticationFail: the failure recovery`, `Checking partmap_info CRC ... `.
- **It halts on failure.** The entire 32 KB image contains exactly **2** infinite spin loops
  (Thumb `b .` = `e7 fe`), at file offsets 0x13bfa and 0x13c02 — immediately adjacent to the
  `Checking partmap_info CRC` string (0x13d1d) and the `AuthenticationFail` recovery string
  (0x13f30). Unlike MBoot, sboot's halts sit directly in its authentication/CRC-failure
  region. (Ghidra's Thumb auto-analysis of this first-stage was poor — the control-flow edge
  from the auth check into the spin was not cleanly recovered — so this is strong structural
  evidence, not a decompiled proof. The spare TV / UART is the way to confirm behaviourally.)

### Stage 2 — MBoot (p2/p3)
Carries a full secure-boot implementation (`_sb_verify_image`, `Secure_verifySignature`,
`lg_sb_verify_image`, `Secure_HaltCPU`), **but** — as documented above — its single halt
primitive is reachable only through `_RawData_Authentication`, which has zero callers, and its
verify functions return status rather than halting. MBoot's own integrity is guaranteed by
sboot having authenticated it before jump. So MBoot doesn't need to re-enforce; Stage 0/1 did.

### Stage 3 — kernel (p21/p22), uImage, uncompressed ARM, `Linux-4.4.84-899.19.koli.1`
- **No runtime integrity whatsoever.** Device-mapper targets compiled in: linear, striped,
  snapshot, delay, error, integrity — **no verity, no crypt**. Symbol count for
  verity/dm-crypt/IMA/EVM/fs-verity = **0**.
- `mount_root` → `mount_block_root` mounts the squashfs rootfs with no signature/hash check
  (decompiled: retries the mount, printk on failure, no verification call).
- The system squashfs images carry no appended dm-verity hash tree (checked swue p6: the
  space after the filesystem is sparse zeros).

### Net answer: are there checks in the BIOS?
**Yes — and they are real and enforcing, but they live in Stage 0/1 (mask ROM + sboot), not
in MBoot or the kernel.** The chain of trust is: ROM verifies sboot, sboot authenticates
OP-TEE + MBoot and halts on failure, MBoot then runs (its own checks non-enforcing because it
was already vouched for), and the kernel does no runtime verification at all.

Practical consequence (unchanged): `boot0` (sboot), `p1` (secureboot), `p2`/`p3` (MBoot) and
the signed kernel image are all inside this chain — modifying any of them fails
sboot/ROM authentication and the set will not boot. **The logo (p25) is outside the chain
entirely**, which is why it is the one safe thing to change.

## Hardware that can stop a boot

| Mechanism | Where | Behaviour |
|---|---|---|
| **SoC mask-ROM auth** | silicon | refuses to run an unsigned/tampered sboot — unrecoverable from flash |
| **sboot authentication** | boot0 | spins (halts) on auth / partmap-CRC failure |
| **MStar WDT** | SoC, reg `0xfd001d48` | hardware watchdog; if boot hangs and it isn't kicked, SoC resets → boot loop. `mstar_wdt_detect_thread` only *logs* expiry to the dump partition; `mstar_arch_reset` (write `0x79` to `0xfd005cb8`) is the reset itself |
| **PM51 power MCU** | separate MCU | issues physical power/reset (`PM51 reboot system`, `Send reset message to PM51`) |
| **MIU memory protection** | SoC | `MIU_HIT_PANIC=OFF` on this set — configured *not* to panic on a protection hit |
| Linux softlockup / panic | kernel | `machine_restart`→`mstar_arch_reset`, `emergency_restart`, `panic` — normal, not tied to partition integrity; no `panic=` reboot timer on the cmdline |

Artifacts: `ghidra/kwdt.txt` (kernel WDT/reset/mount decompiled), `ghidra/sboot.txt`,
`ghidra/kernel-halt-symbols.txt`, plus the symbolized `vmlinux.elf` (68,104 symbols via
kallsyms) in the scratch kernel dir.

---

## Can you boot a custom binary?

Two separate questions with opposite answers.

### Through the boot chain — NO
Every stage is authenticated (see the BIOS chain above):
- Mask ROM verifies sboot; sboot authenticates MBoot and the kernel image.
- Replacing `boot0` (sboot), `p2`/`p3` (MBoot), or the signed kernel (`p21`/`p22`) with a
  custom binary fails signature verification → sboot halts / ROM refuses. Requires LG's
  private signing key, which isn't on the device.
- **kexec (boot a second kernel from the running one, bypassing the bootloader) is NOT
  compiled in.** `sys_kexec_load`, `sys_kexec_file_load`, `compat_sys_kexec_load` all alias to
  `sys_ni_syscall` @0x800520cc (shared with ~70 other disabled syscalls — bpf, userfaultfd,
  mbind, …). CONFIG_KEXEC=n. No kexec path to a custom kernel.

### From within the running system (you already have root) — YES
You don't need to defeat secure boot to run custom code; the authenticated kernel already
runs it for you:
- **Userspace ARM binaries**: trivially — you have root. (Not "booting", but arbitrary custom
  code at full userspace privilege.)
- **Loadable kernel modules (.ko)**: yes. `sys_init_module`/`sys_finit_module`/`load_module`
  present; `modules_disabled` sysctl defaults off; and there is **no module-signature
  verification in this kernel** — `module_sig_check`, `mod_verify_sig`,
  `verify_pkcs7_signature` are all absent, and there's no lockdown LSM. Unsigned modules load
  (tainting the kernel) and run in kernel space. This is full custom code at the privileged
  level, reached from inside the trusted kernel, touching no signed partition.

### Bottom line
You cannot replace the bootloader or kernel with an unsigned custom image and have the chain
boot it — that's exactly what sboot/ROM enforce, and it's why those partitions are brick-risk.
But you can already run arbitrary custom code at both userspace and kernel-module level from
the running system, with no secure-boot fight and no brick risk, because root inside the
authenticated kernel is downstream of every check. A custom *kernel* specifically would need
LG's signing key or a flaw in sboot/MBoot verification — out of scope here.
