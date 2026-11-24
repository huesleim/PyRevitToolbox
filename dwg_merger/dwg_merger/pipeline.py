"""
Top-level orchestration: a folder of source DWGs in, one merged DWG out,
with one flattened layout per source sheet.
"""
import tempfile
from pathlib import Path
from typing import Callable, Optional

import ezdxf

from . import convert
from .flatten import flatten_document

ProgressCallback = Optional[Callable[[int, int, str], None]]


class ConverterNotFoundError(RuntimeError):
    pass


def find_source_dwgs(input_folder: Path):
    return sorted(
        p for p in Path(input_folder).iterdir()
        if p.is_file() and p.suffix.lower() == ".dwg"
    )


def merge_folder(
    input_folder,
    output_dwg_path,
    progress_callback: ProgressCallback = None,
):
    """Reads every .dwg in input_folder, flattens each one's paperspace
    layout(s) into their own layout in a single merged drawing, and writes
    that merged drawing to output_dwg_path.

    progress_callback, if given, is called as (index, total, filename)
    right before each source file is processed.
    """
    convert.configure_bundled_converter()
    if not convert.is_available():
        raise ConverterNotFoundError(
            "ODA File Converter was not found. Expected it bundled next to "
            "this app in an 'ODAFileConverter' folder, or installed system-wide."
        )

    input_folder = Path(input_folder)
    output_dwg_path = Path(output_dwg_path)
    source_files = find_source_dwgs(input_folder)
    if not source_files:
        raise FileNotFoundError(f"No .dwg files found in {input_folder}")

    target_doc = ezdxf.new(convert.DXF_VERSION)

    with tempfile.TemporaryDirectory(prefix="dwg_merger_") as tmp:
        tmp_dir = Path(tmp)

        for i, dwg_path in enumerate(source_files, start=1):
            if progress_callback:
                progress_callback(i, len(source_files), dwg_path.name)

            tmp_dxf = tmp_dir / f"{dwg_path.stem}.dxf"
            convert.dwg_to_dxf(dwg_path, tmp_dxf)
            source_doc = ezdxf.readfile(tmp_dxf)
            flatten_document(source_doc, target_doc, sheet_base_name=dwg_path.stem)

        if "Layout1" in target_doc.layouts.names() and len(target_doc.layouts.names()) > 2:
            target_doc.layouts.delete("Layout1")

        merged_dxf = tmp_dir / "merged.dxf"
        target_doc.saveas(merged_dxf)
        convert.dxf_to_dwg(merged_dxf, output_dwg_path)

    return output_dwg_path
