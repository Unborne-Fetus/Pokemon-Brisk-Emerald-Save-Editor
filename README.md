## License

Brisk Dex's original source code is licensed under the **PolyForm Noncommercial License 1.0.0**.

You are free to study, modify, and redistribute the software for noncommercial purposes, including personal learning, research, experimentation, and hobby projects.

**Commercial use is not permitted under this license.** This includes using Brisk Dex or derivative works for commercial purposes or selling copies or derivative versions.

Pokémon-related names, assets, artwork, game data, trademarks, and other material belonging to third parties are **not** licensed by this notice and remain the property of their respective owners.

See the `LICENSE` file for the complete license terms.



Made with Claude vibe coding


# Brisk Dex Desktop

The desktop build of Brisk Dex — the companion app for Pokémon Brisk Emerald.
This reads and edits `.sav` files directly on disk (with automatic timestamped
backups) and keeps an external Pokémon storage file independent of any single save.

## What you need first

- **Node.js** (LTS, v18 or newer). If you don't have it: https://nodejs.org
  Check you have it with:
  ```
  node -v
  ```

## Build it (one click)

- **Windows:** double-click `build.bat`.
- **Mac/Linux:** double-click `build.sh` (or run `./build.sh` in a terminal —
  you may need to right-click → "Open" the first time on macOS to get past
  Gatekeeper, or run `chmod +x build.sh` once on Linux).

Either script installs everything needed and builds the installer for you —
no typing npm commands required. The finished installer lands in `dist/`.
Remember: this build step is only for you, the developer. The players who
download the resulting `.exe` never need Node, npm, or any of this — they
just run the installer.

## Build it manually (if you'd rather run the steps yourself)

Open a terminal in this folder and run:

```bash
npm install
```

That downloads Electron and electron-builder (this step needs internet access
and may take a few minutes the first time).

To just try the app without building an installer:

```bash
npm start
```

To build the actual installer:

```bash
npm run dist
```

The output lands in `dist/`. On Windows this produces an NSIS installer
(`Brisk Dex Setup 1.0.0.exe`) — run it to install the app like any other
Windows program, with a Start Menu shortcut and everything.

### Building the Windows .exe from macOS or Linux

`electron-builder` can cross-build a Windows installer from macOS or Linux,
but it needs **Wine** installed on that machine:

```bash
npm run dist:win
```

If you're on Windows itself, `npm run dist` (or `npm run dist:win`) just works
with no extra setup.

### Other platforms

```bash
npm run dist:mac     # macOS .dmg (must be run on macOS)
npm run dist:linux    # Linux AppImage
```

## Getting your real Brisk Emerald data (species, moves, abilities, items, icons)

Brisk Dex ships with vanilla Gen I–III species names/types as a baseline, but
your hack almost certainly renumbers and adds a lot more than that. There's a
converter script included for this:

```bash
python3 tools/extract_data.py /path/to/your/Pokemon-Brisk-Emerald/checkout
```

(No dependencies beyond Python 3 — it just reads your source files, it never
touches the network.) It produces two things in the folder you ran it from:

- `brisk-dex-data.json` — species names/types/abilities, move names, ability
  names, and item names, all pulled straight from your `include/constants/*.h`
  and `src/data/*.h` files.
- `brisk-dex-icons/` — your actual icon.png art for every species that has a
  matching `graphics/pokemon/<name>/icon.png`, copied and renamed by species ID.

Then in Brisk Dex:

1. **Load species/move data** → pick `brisk-dex-data.json`. This overrides/extends
   the built-in vanilla baseline with your real data (custom species keep their
   real name/types/abilities; move and item names appear instead of "Move #45").
2. **Load icon folder** → pick the `brisk-dex-icons` folder. Do this *after*
   step 1, so icon files get matched to the right species IDs. (You can also
   point this directly at your repo's `graphics/pokemon` folder instead of the
   extracted copy — Brisk Dex will match subfolder names to species constants
   on its own.)

If your repo's file layout doesn't quite match what the script expects (e.g.
you've moved `species_info.h` somewhere nonstandard, or a version of expansion
changed the struct field names), it'll still write out whatever it could match
and print counts + a warning — share those details and I can adjust the script.



- `main.js` — the Electron main process. Opens native file dialogs, reads/writes
  the `.sav` file on disk, and stores external Pokémon storage as a JSON file
  in your OS's app-data folder.
- `preload.js` — exposes a small, safe `window.briskDexAPI` to the app (no raw
  Node/filesystem access is given to the page itself).
- `index.html` — the entire app (UI + Gen III save parser). This is the exact
  same file used by the browser/web version of Brisk Dex, so both stay in sync.

## Safety notes

- Every time you save changes to a `.sav` file, the app first copies your
  existing file to `<name>.backup-<timestamp>.sav` in the same folder, then
  writes the new version. If anything ever looks wrong, restore from that
  backup.
- External storage lives at (OS-dependent app data folder)/Brisk Dex/briskdex-storage.json,
  independent of any game save — that's what lets you deposit from one save
  file and withdraw into a different one for cross-save trading.
