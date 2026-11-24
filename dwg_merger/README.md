# DWG Sheet Merger

Takes a folder of sheet DWGs (e.g. exported from Revit) and produces one
merged DWG with one layout per source sheet. Each layout contains exactly
what that sheet's viewport(s) show — clipped and flattened, the same way
ArchiCAD's "Export Paper Space with merged viewport content" behaves —
plus any title block/notes that live directly in paperspace.

No paid software required: [ODA File Converter](https://www.opendesign.com/guestfiles/oda_file_converter)
(free) handles DWG↔DXF, and `ezdxf` + `shapely` (both open source) do the
actual geometry work.

## Running it (developer machine)

```
pip install -r requirements.txt
python main_gui.py        # GUI: pick a folder, pick an output file, Merge
python main_cli.py <input_folder> <output.dwg>   # same thing, no GUI
```

Requires ODA File Converter to be installed system-wide (default path:
`C:\Program Files\ODA\ODAFileConverter\ODAFileConverter.exe`) unless you've
bundled a copy per the packaging step below.

## Distributing to the office (no installs on colleagues' machines)

1. Run `build_exe.bat` on your machine. This needs Python + pip once, to
   produce the standalone build — colleagues never need it.
2. Follow the printed instructions to copy your ODA File Converter install
   into `dist\DWGMerger\ODAFileConverter\`.
3. Zip `dist\DWGMerger` and hand it out. Colleagues run `DWGMerger.exe`
   directly. No Python, no ODA, no install step on their end.

`dwg_merger/convert.py` looks for that bundled `ODAFileConverter` folder
next to the running exe first, and only falls back to a system-wide
install if it's not there — so this works identically on your dev machine
and on a colleague's clean machine.

## How it works

```
dwg_merger/
├── viewport.py    modelspace -> paperspace transform, and each
│                  viewport's clip boundary (rectangular or VPCLIP polygon)
├── clipping.py     clips one entity against that boundary
├── flatten.py       drives one source drawing's layout(s) into the target
├── convert.py        DWG <-> DXF via ODA File Converter (through ezdxf)
└── pipeline.py         folder-of-DWGs -> merged-DWG orchestration
```

Per source file: convert DWG→DXF, then for each of its paperspace layouts,
for each viewport on that layout, every modelspace entity is transformed
into paperspace coordinates and clipped against that viewport's boundary.
Entities fully inside are kept as-is; fully outside are dropped; entities
straddling the boundary are actually re-clipped (not just transformed) for
LINE, LWPOLYLINE, and single-loop HATCH. Non-viewport paperspace content
(title blocks, sheet text) is copied through untouched.

## Known limitations

True geometric clipping for every possible entity type is a genuinely hard
problem — even Autodesk's own `EXPORTLAYOUT` command, which does the same
kind of flattening, has documented fidelity gaps (wide polylines not
trimming cleanly, objects getting exploded/converted to be trimmed at all).
This tool takes the same practical approach:

- **Real clipping**: LINE, LWPOLYLINE (open or closed), single-loop HATCH.
- **All-or-nothing** (kept whole if its bounding box touches the viewport
  boundary at all, dropped otherwise): CIRCLE, ARC, TEXT, MTEXT,
  DIMENSION, INSERT (blocks), SPLINE, and any HATCH with islands/holes
  (more than one boundary loop).
- Viewport view-twist (rotated views) is handled in the transform math but
  untested against a real rotated viewport — most architectural sheets
  don't use it, but check output carefully if yours do.

If a sheet's straddling geometry is mostly lines/polylines/hatches (walls,
poché, room outlines — the bulk of a typical floor plan), this should
closely match what ArchiCAD produces. Sheets relying heavily on clipped
blocks or wide polylines crossing the viewport edge are where you'll see
the biggest gap, and are worth a visual check after merging.
