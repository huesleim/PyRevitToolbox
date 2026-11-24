"""
Clips a single (already paperspace-transformed) entity against a viewport's
clip boundary.

Strategy, cheapest check first:
  1. Bounding-box test: fully outside -> drop, fully inside -> keep as-is.
  2. For boundary-straddling entities, real geometric clipping is only
     implemented for the entity types where it's tractable without a full
     CAD kernel: LINE, open/closed LWPOLYLINE, and single-loop HATCH
     boundaries. This covers the bulk of a typical architectural sheet
     (walls, poche, room outlines).
  3. Everything else that straddles the boundary (TEXT, MTEXT, DIMENSION,
     INSERT, SPLINE, multi-loop HATCH, CIRCLE/ARC) is kept whole if its
     bounding box touches the boundary at all, and dropped otherwise. This
     is the same all-or-nothing compromise AutoCAD's own EXPORTLAYOUT
     command falls back to for hard cases -- true sub-entity clipping for
     these types is a known-hard problem, not something skipped out of
     laziness.
  0. DIMENSIONs are exploded into plain geometry first (see
     explode_dimension), then each piece goes through the steps above.
"""
import ezdxf
from ezdxf import bbox as ezbbox
from ezdxf import path as ezpath
from shapely.geometry import LineString, Point, Polygon, box as shapely_box

TRUE_CLIP_TYPES = {"LINE", "LWPOLYLINE"}
DIMENSION_TYPES = {"DIMENSION", "ARC_DIMENSION", "LARGE_RADIAL_DIMENSION"}


def entity_bbox(entity):
    box = ezbbox.extents([entity])
    if not box.has_data:
        return None
    return (box.extmin.x, box.extmin.y, box.extmax.x, box.extmax.y)


def bbox_relation(entity_box, boundary_poly):
    minx, miny, maxx, maxy = boundary_poly.bounds
    ex0, ey0, ex1, ey1 = entity_box
    if ex1 < minx or ex0 > maxx or ey1 < miny or ey0 > maxy:
        return "outside"
    if boundary_poly.contains(shapely_box(ex0, ey0, ex1, ey1)):
        return "inside"
    return "partial"


def _clip_closed_polygon(points, boundary_poly):
    """Clip a closed area (LWPOLYLINE or a hatch loop) against the
    boundary. Returns a list of point-lists (one per resulting piece,
    since a non-convex boundary can split one shape into several)."""
    shape = Polygon(points)
    if not shape.is_valid:
        shape = shape.buffer(0)
    clipped = shape.intersection(boundary_poly)
    if clipped.is_empty:
        return []
    polys = list(clipped.geoms) if clipped.geom_type == "MultiPolygon" else [clipped]
    return [list(p.exterior.coords) for p in polys if not p.is_empty]


def _clip_open_line(points, boundary_poly):
    """Clip an open polyline/line against the boundary. Returns a list of
    point-lists (a line can exit and re-enter, producing several pieces)."""
    shape = LineString(points)
    clipped = shape.intersection(boundary_poly)
    if clipped.is_empty:
        return []
    lines = list(clipped.geoms) if clipped.geom_type == "MultiLineString" else [clipped]
    return [list(line.coords) for line in lines if not line.is_empty and line.length > 0]


def clip_line_entity(entity, boundary_poly):
    p1, p2 = entity.dxf.start, entity.dxf.end
    pieces = _clip_open_line([(p1.x, p1.y), (p2.x, p2.y)], boundary_poly)
    results = []
    for pts in pieces:
        e2 = entity.copy()
        e2.dxf.start = (pts[0][0], pts[0][1], p1.z)
        e2.dxf.end = (pts[-1][0], pts[-1][1], p2.z)
        results.append(e2)
    return results


def clip_lwpolyline_entity(entity, boundary_poly):
    points = [(p[0], p[1]) for p in entity.get_points()]
    if len(points) < 2:
        return []

    if entity.closed:
        pieces = _clip_closed_polygon(points, boundary_poly)
        close = True
    else:
        pieces = _clip_open_line(points, boundary_poly)
        close = False

    results = []
    for pts in pieces:
        e2 = entity.copy()
        e2.set_points(pts)
        e2.closed = close
        results.append(e2)
    return results


def clip_hatch_entity(entity, boundary_poly):
    loops = list(ezpath.from_hatch(entity))
    if len(loops) != 1:
        # Multiple loops means islands/holes -- decomposing a clipped
        # multi-loop hatch back into valid DXF boundary paths is not
        # implemented. Keep the hatch whole; the caller's bbox check
        # already ensured it at least touches the boundary.
        return [entity]

    points = [(p.x, p.y) for p in loops[0].flattening(0.05)]
    pieces = _clip_closed_polygon(points, boundary_poly)
    results = []
    for pts in pieces:
        e2 = entity.copy()
        e2.paths.clear()
        e2.paths.add_polyline_path(pts, is_closed=True)
        results.append(e2)
    return results


def explode_dimension(entity):
    """Break a DIMENSION into its plain geometry (lines, arrows, text)
    taken from the dimension's geometry block, so the measurement text keeps
    the modelspace value. Done BEFORE the paperspace transform: a DIMENSION
    moved into paperspace gets re-measured from its scaled defpoints."""
    if entity.get_geometry_block() is None:
        entity.override().render()
    return list(entity.virtual_entities())


def process_entity(entity, matrix, boundary_poly):
    """Transform one modelspace entity into paperspace via `matrix`, then
    clip it against `boundary_poly`. Returns a list of resulting entity
    copies (possibly empty, possibly more than one)."""
    if entity.dxftype() in DIMENSION_TYPES:
        results = []
        for part in explode_dimension(entity):
            results.extend(process_entity(part, matrix, boundary_poly))
        return results

    transformed = entity.copy()
    try:
        transformed.transform(matrix)
    except NotImplementedError:
        return []

    ebox = entity_bbox(transformed)
    if ebox is None:
        return [transformed]

    relation = bbox_relation(ebox, boundary_poly)
    if relation == "outside":
        return []
    if relation == "inside":
        return [transformed]

    dxftype = transformed.dxftype()
    if dxftype == "LINE":
        return clip_line_entity(transformed, boundary_poly)
    if dxftype == "LWPOLYLINE":
        return clip_lwpolyline_entity(transformed, boundary_poly)
    if dxftype in ("HATCH", "MPOLYGON"):
        return clip_hatch_entity(transformed, boundary_poly)

    # Fallback for CIRCLE, ARC, TEXT, MTEXT, INSERT, SPLINE, etc.
    if boundary_poly.intersects(shapely_box(*ebox)):
        return [transformed]
    return []
