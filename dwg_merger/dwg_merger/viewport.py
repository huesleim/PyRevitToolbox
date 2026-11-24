"""
Viewport math: the modelspace -> paperspace transform a VIEWPORT applies,
and the paperspace clip boundary (rectangular or VPCLIP polygon) that
limits what "shows through" that viewport.
"""
import math

import ezdxf
from ezdxf.math import Matrix44
from shapely.geometry import Polygon, box as shapely_box

# DXF VIEWPORT group code 90 (flags) bit that means "non-rectangular clipping
# is active" -- see ezdxf.entities.viewport.acdb_viewport_group_codes.
NON_RECT_CLIP_FLAG = 0x10000

# The VIEWPORT with id == 1 is the mandatory "background" viewport every
# paperspace layout has; it represents the layout tab itself, not a real
# printed window into modelspace, and must be skipped.
BACKGROUND_VIEWPORT_ID = 1


def real_viewports(layout):
    """Return the VIEWPORT entities on a layout that represent actual
    printed windows (excludes the background viewport and any turned off)."""
    return [
        vp for vp in layout.query("VIEWPORT")
        if vp.dxf.id != BACKGROUND_VIEWPORT_ID and vp.dxf.status != 0
    ]


def viewport_transform(vp) -> Matrix44:
    """Matrix that maps modelspace points, as seen through this viewport,
    into paperspace (sheet) coordinates."""
    scale = vp.dxf.height / vp.dxf.view_height
    twist = math.radians(vp.dxf.view_twist_angle or 0.0)
    vcx, vcy, _ = vp.dxf.view_center_point
    cx, cy, _ = vp.dxf.center

    m = Matrix44.translate(-vcx, -vcy, 0)
    if twist:
        m = m @ Matrix44.z_rotate(-twist)
    m = m @ Matrix44.scale(scale, scale, 1)
    m = m @ Matrix44.translate(cx, cy, 0)
    return m


def viewport_boundary(vp, source_doc):
    """The clip boundary for this viewport, as a shapely Polygon in
    paperspace coordinates (the same space the viewport rectangle itself
    lives in).

    Rectangular viewports: a simple rectangle from center/width/height.
    VPCLIP'd viewports: the referenced boundary entity (LWPOLYLINE, CIRCLE,
    ELLIPSE, or closed SPLINE), flattened to a polygon.
    """
    flags = vp.dxf.flags or 0
    handle = vp.dxf.get("clipping_boundary_handle", "0")

    if flags & NON_RECT_CLIP_FLAG and handle and handle != "0":
        boundary_entity = source_doc.entitydb.get(handle)
        if boundary_entity is not None:
            path = ezdxf.path.make_path(boundary_entity)
            points = [(p.x, p.y) for p in path.flattening(0.05)]
            if len(points) >= 3:
                poly = Polygon(points)
                if poly.is_valid and not poly.is_empty:
                    return poly

    cx, cy, _ = vp.dxf.center
    w, h = vp.dxf.width, vp.dxf.height
    return shapely_box(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
