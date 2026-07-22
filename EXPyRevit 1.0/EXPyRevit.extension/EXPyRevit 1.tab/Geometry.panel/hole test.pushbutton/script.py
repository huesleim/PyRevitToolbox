# -*- coding: utf-8 -*-
from Autodesk.Revit.UI.Selection import ObjectType, ISelectionFilter
from Autodesk.Revit.Exceptions import OperationCanceledException
from Autodesk.Revit.DB import BuiltInCategory, Floor
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
    floor_type_id = floor.GetTypeId()
    flor_level_id = floor.LevelId
    
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
    curves_output = []

    for i in polygon_relationship:
        merged_curves = []
        smallest_area = float("inf")
        closest_parent = None

        if not polygon_relationship[i]:
            continue

        for j in polygon_relationship[i]:
            area_j = curve_array_objects_dict[j]["area"] 
            if area_j < smallest_area:
                smallest_area: area_j
                closest_parent = j
        
        if closest_parent is not None:
            merged_curves.extend(curve_array_objects_dict[closest_parent]["curves"])
        merged_curves.extend(curve_array_objects_dict[i]["curves"])

        curves_output.append(merged_curves)

    return curves_output


def create_floors (merged_curves, floor):
    try:
        t = Transaction(doc, "Separate floor")
        t.Start()

        for curve_array in merged_curves:
            cl = CurveLoop()
            for curve in curve_array:
                cl.Append(c)


            Floor.Create(
                doc,
                [cl],
                floor.GetTypeId(),
                floor.LevelId
            )
        doc.Delete(floor.Id)

        t.Commit()
            
    except OperationCanceledException:
        print("Selection cancelled.")

    except Exception:
        traceback.print_exc()
