"""
Turns a source drawing's paperspace layout(s) into flattened layouts in a
target drawing: everything a viewport shows gets clipped + transformed into
sheet coordinates, and non-viewport paperspace content (title blocks, sheet
notes) is copied through untouched.
"""
import re

from ezdxf.addons import Importer

from .clipping import process_entity
from .viewport import real_viewports, viewport_boundary, viewport_transform

_ILLEGAL_NAME_CHARS = re.compile(r'[<>/\\":;?*|=`,]')
MAX_LAYOUT_NAME_LEN = 255


def sanitize_layout_name(name: str) -> str:
    name = _ILLEGAL_NAME_CHARS.sub("_", name).strip()
    return name[:MAX_LAYOUT_NAME_LEN] or "Sheet"


def unique_layout_name(target_doc, base_name: str) -> str:
    existing = set(target_doc.layouts.names())
    name = base_name
    counter = 2
    while name in existing:
        suffix = f"_{counter}"
        name = base_name[: MAX_LAYOUT_NAME_LEN - len(suffix)] + suffix
        counter += 1
    return name


def flatten_layout(source_doc, source_layout, target_doc, target_layout_name):
    """Flattens one paperspace layout of source_doc into a new layout named
    target_layout_name in target_doc. Returns the new target layout."""
    layout_name = unique_layout_name(target_doc, sanitize_layout_name(target_layout_name))
    target_layout = target_doc.layouts.new(layout_name)

    to_import = []
    for vp in real_viewports(source_layout):
        matrix = viewport_transform(vp)
        boundary = viewport_boundary(vp, source_doc)
        for entity in source_doc.modelspace():
            to_import.extend(process_entity(entity, matrix, boundary))

    for entity in source_layout:
        if entity.dxftype() != "VIEWPORT":
            to_import.append(entity.copy())

    if to_import:
        importer = Importer(source_doc, target_doc)
        importer.import_entities(to_import, target_layout=target_layout)
        importer.finalize()

    return target_layout


def paperspace_layout_names(doc):
    """All layout names in a document except modelspace itself, in the
    order they appear on the layout tabs."""
    return [name for name in doc.layouts.names_in_taborder() if name != "Model"]


def flatten_document(source_doc, target_doc, sheet_base_name):
    """Flattens every paperspace layout in source_doc into target_doc.
    Layouts are named '<sheet_base_name>' for a single-layout source, or
    '<sheet_base_name>_<layout>' when the source has several."""
    names = paperspace_layout_names(source_doc)
    single = len(names) == 1
    created = []
    for name in names:
        source_layout = source_doc.layouts.get(name)
        target_name = sheet_base_name if single else f"{sheet_base_name}_{name}"
        created.append(flatten_layout(source_doc, source_layout, target_doc, target_name))
    return created
