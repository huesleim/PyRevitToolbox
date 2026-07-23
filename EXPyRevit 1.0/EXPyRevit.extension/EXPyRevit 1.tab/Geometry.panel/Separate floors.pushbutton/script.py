# -*- coding: utf-8 -*-
from Autodesk.Revit.UI.Selection import ObjectType, ISelectionFilter
from Autodesk.Revit.Exceptions import OperationCanceledException
from Autodesk.Revit.DB import Floor, Transaction, CurveLoop
import traceback

uidoc = __revit__.ActiveUIDocument
doc = uidoc.Document

class FloorSelectionFilter(ISelectionFilter):
    def AllowElement(self, elem):
        return isinstance(elem, Floor)

    def AllowReference(self, reference, position):
        return False

def pick_floor():
    ref = uidoc.Selection.PickObject(
        ObjectType.Element,
        FloorSelectionFilter(),
        "Pick a floor"
    )
    return doc.GetElement(ref.ElementId)

def area_calc(points):
    n = len(points)
    area = 0.0
    for i in range(n):
        x0, y0 = points[i].X, points[i].Y
        x1, y1 = points[(i+1) % n].X, points[(i+1) % n].Y
        area += (x0 * y1) - (x1 * y0)
    return abs(area) / 2

def process_floors(floor):
    
    curve_array_objects_dict = {}

    sketch = doc.GetElement(floor.SketchId)
    profile = sketch.Profile

    for i, curve_array in enumerate(profile):
        
        curve_array_dict = {}
        curve_array_dict["curves"] = curve_array 
        
        points_list = []

        for j, curve in enumerate(curve_array):
            tessellated_points = curve.Tessellate()
            points_list.extend(tessellated_points)
        
        curve_array_dict["points"] = points_list
        curve_array_dict["area"] = area_calc(points_list)
        curve_array_objects_dict[i] = curve_array_dict
    
    return curve_array_objects_dict

def point_in_polygon_points(point, polygon_points):
    x, y = point.X, point.Y
    n = len(polygon_points)
    k = n-1

    inside = False

    for l in range(n):
        xl, yl = polygon_points[l].X, polygon_points[l].Y
        xk, yk = polygon_points[k].X, polygon_points[k].Y

        intersects = ((yl > y) != (yk > y)) and (
            x < (xk - xl) * (y - yl) / (yk - yl) + xl
        )

        if intersects:
            inside = not inside
        
        k = l
        
    return inside

def compare_all_polygons(curve_array_objects_dict):
    polygon_relationship = {}
    for i in curve_array_objects_dict:
        polygon_parents = []

        for j in curve_array_objects_dict:
            if i == j:
                continue
            point = curve_array_objects_dict[i]["points"][0]
            polygon_points = curve_array_objects_dict[j]["points"]
            result = point_in_polygon_points(point, polygon_points)

            if result: polygon_parents.append(j)
        polygon_relationship[i] = polygon_parents
    return polygon_relationship

def resolve_parentship(polygon_relationship, curve_array_objects_dict):
    parentship = {}

    for i in polygon_relationship:
        
        smallest_area = float("inf")
        closest_parent = None

        for j in polygon_relationship[i]:
            area_j = curve_array_objects_dict[j]["area"] 
            
            if area_j < smallest_area:
                smallest_area = area_j
                closest_parent = j
        
        parentship.setdefault(closest_parent, []).append(i)

    return parentship

def build_floor_groups(loop, parentship, curve_array_objects_dict):

    # This floor starts with its outer boundary
    profile = [curve_array_objects_dict[loop]["curves"]]

    # Direct children are holes of this floor
    children = parentship.get(loop, [])

    for child in children:
        profile.append(curve_array_objects_dict[child]["curves"])

    # First result is this floor
    groups = [profile]

    # Grandchildren start new floors
    for child in children:
        for grandchild in parentship.get(child, []):
            groups.extend(
                build_floor_groups(grandchild, parentship, curve_array_objects_dict)
            )

    return groups

def create_floors(floor, parentship, curve_array_objects_dict):
    t = Transaction(doc, "Separate floor")
    t.Start()

    try:
        roots = parentship.get(None, [])
        floor_groups = []
        for root in roots:
            floor_groups.extend(build_floor_groups(root, parentship, curve_array_objects_dict))

        floor_type_id = floor.GetTypeId()
        floor_level_id = floor.LevelId

        for group in floor_groups:
            curve_loops = []
            for curve_array in group:
                cl = CurveLoop()
                for c in curve_array:
                    cl.Append(c)
                curve_loops.append(cl)

            Floor.Create(doc, curve_loops, floor_type_id, floor_level_id)

        doc.Delete(floor.Id)
        t.Commit()

    except Exception:
        t.RollBack()
        traceback.print_exc()


try:
    floor = pick_floor()
    curve_array_objects_dict = process_floors(floor)
    polygon_relationship = compare_all_polygons(curve_array_objects_dict)
    parentship = resolve_parentship(polygon_relationship, curve_array_objects_dict)
    create_floors(floor, parentship, curve_array_objects_dict)

except OperationCanceledException:
    print("Selection cancelled.")

except Exception:
    traceback.print_exc()