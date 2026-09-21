# G1-Emu on this machine (humans & agents)

This document describes **this Mac’s working setup** for
[`G1-Emu`](https://github.com/animatek/G1-Emu). It supplements the project
[`README.md`](../README.md) (upstream build/use docs), not replace it.

**Repo:** `/Users/bcsantos/Development/G1-Emu`  
**Last verified:** 2026-09-21 (macOS Monterey 12.7.6, Intel x86_64)

---

## For agents (read first)

| Item | Value |
| --- | --- |
| Package manager | **MacPorts only** — do not use Homebrew on this machine |
| Sudo | User runs MacPorts installs (`sudo port install …`); agent asks, does not assume |
| ROM | Present at `Roms/NORD-MODULAR-RACK-VER-3.03.BIN` — **never commit** (gitignored) |
| Gearmulator | `~/src/gearmulator-md-mm` @ tag `mdmm-v0.1.0-alpha.13` (submodules) |
| JUCE | `/Users/bcsantos/Development/Animatek-NME/JUCE` (8.0.12) |
| NME (patchtest only) | `/Users/bcsantos/Development/Animatek-NME` |
| Build dir | `build/` (Release, JUCE backend on macOS) |
| Flash / settings | `~/.local/share/Animatek/G1-Emu/flash.bin`, `settings.conf` |
| Official Clavia packages | `Roms/official-updater/` (reference only; not a ROM source) |

**Do not:** download ROMs from forums or third parties; modify `~/src/gearmulator-md-mm`;
run destructive git commands without explicit request.

**Smoke test (no GUI):**

```bash
cd /Users/bcsantos/Development/G1-Emu
./g1.sh
# Expect: flash loaded, MIDI ports, audio line, periodic [Ns] status; Ctrl+C saves flash
```

**Rebuild (if sources change):**

```bash
cmake --build build -j2
```

Reconfigure only if dependencies move:

```bash
cmake -B build -DCMAKE_BUILD_TYPE=Release \
  -DGEARMULATOR_DIR="$HOME/src/gearmulator-md-mm" \
  -DG1_JUCE_DIR="/Users/bcsantos/Development/Animatek-NME/JUCE" \
  -DNME_DIR="/Users/bcsantos/Development/Animatek-NME"
```

---

## Machine profile

| | |
| --- | --- |
| OS | macOS Monterey 12.7.6 |
| CPU | Intel x86_64, 4 cores |
| RAM | 4 GB (use `-j2` when building; real-time load often ~100%) |
| Xcode | 14.2 |
| CMake | MacPorts 3.31.x (`/opt/local/bin/cmake`) |
| Archive tools | MacPorts `unar` (`/opt/local/bin/unar`) for StuffIt on host |

---

## What was set up here

1. **Gearmulator** cloned to `~/src/gearmulator-md-mm` (required; not in repo).
2. **Built** G1-Emu Release with JUCE backend (macOS default).
3. **ROM** placed in `Roms/NORD-MODULAR-RACK-VER-3.03.BIN` — validated:
   - 512 KB, rack model byte `0x01` at `0x7FF`
   - SHA256 `d9b199f27f573fdf7cd985fbd33cb9e60893a08912ab5d1bb562c77c663c997e`
   - Matches fingerprint in project `NOTES.md`
4. **First run** created flash from factory OS in ROM.
5. **Launch scripts** `g1.sh` / `g1gui.sh` executable; `g1gui.sh` picks macOS `.app` bundle path.

### ROM vs official updater (provenance)

Nord’s site hosts **OS v3.03b update packages** (`.hqx` / `.zip`), not a raw `.BIN`.
Those files are kept under `Roms/official-updater/` for reference.

Analysis showed the updater embeds a **`Clavia OS update file V1.0`** payload (encrypted
MIDI flash-update stream). It is **not** the 512 KB boot ROM G1-Emu needs. A hardware
or otherwise legitimate **ROM dump** is required to run the emulator.

Optional helper (payload extraction only, no ROM rebuild):

```bash
python3 tools/extract_clavia_update.py \
  "Roms/official-updater/win/Nord Modular OS v3.03b Update.exe" \
  -o /tmp/modular-update-payload.bin
```

---

## Running

```bash
cd /Users/bcsantos/Development/G1-Emu
./g1gui.sh   # panel window (JUCE)
./g1.sh      # console; status lines only (DSP log filtered)
```

**First GUI launch on macOS:** Gatekeeper may block the unsigned app. Right-click → Open,
or: `xattr -dr com.apple.quarantine build/app/gui/g1gui_artefacts/Release/G1-Emu.app`

### macOS privacy (microphone prompt)

JUCE opens **audio input** for the emulated back-panel inputs (`in_L` / `in_R`). macOS
asks **“Terminal would like to access the microphone.”** That is CoreAudio input permission,
not a literal mic recording.

- **Allow:** full 4-out / 2-in behavior.
- **Don’t allow:** outputs + MIDI still work; inputs stay disabled (verified).

Change later: **System Settings → Privacy & Security → Microphone**.

### Performance on this Mac

Four DSP56303s at real clock often report **load ~100%** and **speed 10–50%** of real time.
If audio glitches, try serial DSPs: `G1_THREADS=0 ./g1.sh`

---

## MIDI & audio (macOS / JUCE)

While running, CoreMIDI exposes:

| Port | Purpose |
| --- | --- |
| **G1-Emu PC Port** | Editor protocol (patch upload, SysEx) — **not** normal note MIDI |
| **G1-Emu MIDI** | Notes, CC, program change — **DAW goes here** |

Check **Audio MIDI Setup → MIDI Studio** if a host app does not list them.

Audio: default **Built-in Output**, 48 kHz, stereo outs 1/2, +36 dB gain (undoes OS −36 dB cap).
Change driver/device in **Settings** (GUI) or `settings.conf`; see project `CLAUDE.md` for `G1_*` env vars.

---

## Factory presets (local)

**211** factory `.pch` files from the
[electro-music Nord Modular Classic Archive](https://electro-music.com/nm_classic/011_9_Factory_Presets/)
(all directories under `011_9_Factory_Presets/`):

```text
patches/factory/
  1.10/              100 patches  (OS 1.10 factory bank — full set on electro-music)
  2.00/               20 patches
  2.10/               22 patches
  3.03/               21 patches  (partial; not the full 100-slot 3.03 flash bank)
  stereo-compress/     4 patches
  random/             15 patches
  micro-modular/      29 patches  (Micro Modular factory; not the rack)
```

**Important:** electro-music does **not** host a complete 100-patch **3.03** rack
factory bank as individual files — only 21 for that folder. The **1.10** folder
is the only full 100-preset set on the site. OS 3.03 can read many 2.1+ patches;
older ones may need conversion in a legacy editor (see electro-music FAQ).

For **rack + OS 3.03**, start with `patches/factory/3.03/`; add `2.10/`, `2.00/`,
or `random/` as needed.

Headless smoke test (needs NME tree and a built `g1patchtest`):

```bash
./build/tools/patchtest/g1patchtest_artefacts/Release/g1patchtest \
  Roms/NORD-MODULAR-RACK-VER-3.03.BIN patches/factory/3.03/MoogBass05.pch --note 60 --seconds 2
```

## Loading a patch

The emulator **does not** open `.pch` files by itself. Same as hardware:

1. Start `./g1gui.sh` or `./g1.sh`.
2. Open a G1 editor (e.g. [Animatek NME](../README.md#using-it)).
3. Set editor MIDI **in and out** to **G1-Emu PC Port**.
4. Open a `.pch` from `patches/factory/` (or anywhere) and **upload** to the synth.

Patches can persist in flash after upload; quit cleanly (Ctrl+C or close GUI) to save
`~/.local/share/Animatek/G1-Emu/flash.bin`.

---

## Ableton Live (or any DAW)

- **Patch load:** editor on **PC Port** (Live cannot upload `.pch` files).
- **Play sequences:** Live MIDI track → **MIDI To: G1-Emu MIDI**.
- Enable the port under **Preferences → Link / Tempo / MIDI** (Track + Remote as needed).

Both editor and Live can be connected simultaneously.

---

## Related paths (outside this repo)

| Path | Notes |
| --- | --- |
| `~/src/gearmulator-md-mm` | Gearmulator core (GPLv3); do not edit |
| `~/Development/Animatek-NME/` | JUCE + NME; `-DG1_JUCE_DIR`, `-DNME_DIR` |
| `/Volumes/macOS_Monterey_Xtras/basilisk_files/Myst-System753.dsk` | System 7.5.3 + StuffIt Expander 5.5 (Basilisk); for Mac archive work, not required to run G1-Emu |
| `~/Documents/Animatek/G1-Emu/roms/` | Alternate ROM search path (romfinder) |

---

## Troubleshooting

| Symptom | Check |
| --- | --- |
| “needs the 512 KB ROM” | `Roms/NORD-MODULAR-RACK-VER-3.03.BIN` exists and is 524288 bytes |
| No MIDI ports in DAW | G1-Emu running; MIDI Studio shows G1-Emu ports |
| No sound | Patch uploaded? Note on **MIDI** port? Audio device in Settings |
| GUI won’t start | Gatekeeper / quarantine; see above |
| Heavy stutter | `G1_THREADS=0`; close other CPU-heavy apps; 4 GB RAM is tight |
| Inputs dead | Microphone permission denied for Terminal — expected |

---

## Project docs (upstream)

| File | Content |
| --- | --- |
| [`README.md`](../README.md) | Official build & use |
| [`CLAUDE.md`](../CLAUDE.md) | Maintainer/agent project rules |
| [`NOTES.md`](../NOTES.md) | Hardware & OS reverse-engineering |
| [`ROADMAP.md`](../ROADMAP.md) | Planned work |

When changing code that goes upstream, follow project rules: English only, `CHANGELOG.md`
entry in the same commit, ROMs never in git.
