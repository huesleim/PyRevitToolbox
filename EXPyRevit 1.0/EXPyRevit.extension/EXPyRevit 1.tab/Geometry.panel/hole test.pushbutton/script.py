# -*- coding: utf-8 -*-
from Autodesk.Revit.UI.Selection import ObjectType
from Autodesk.Revit.Exceptions import OperationCanceledException
from Autodesk.Revit.DB import BuiltInCategory
import traceback

uidoc = __revit__.ActiveUIDocument
doc = uidoc.Document

def tesellated_cache (loop_dic):
    if loop_dic["points"] is None:
        points = []
        for curve in loop_dic["curves"]:
            points.extend(curve.Tessellate())
        loop_dic["points"] = points
    return loop_dic["points"]

def point_in_polygon_points(point, polygon_points):
    x, y = point.X, point.Y
    n = len(polygon_points)
    inside = False

    j = n - 1
    for i in range(n):
        xi, yi = polygon_points[i].X, polygon_points[i].Y
        xj, yj = polygon_points[j].X, polygon_points[j].Y
        intersects = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / (yj - yi) + xi
        )

        if intersects:
            inside = not inside

        j = i

    return inside


try: 
    ref = uidoc.Selection.PickObject(ObjectType.Element, "Pick a floor")
    floor = doc.GetElement(ref.ElementId)
    if floor.Category.Id.IntegerValue != int(BuiltInCategory.OST_Floors):
        print ("Not a floor!")

    else:
        sketch = doc.GetElement(floor.SketchId)

        floor_input = []
        floor_output = []
        floor_type_id = floor.GetTypeId()
        floor_level_id = floor.LevelId

        inside = False

        #populating floor_input with curves and points
        for loop_index, profile_loop in enumerate(sketch.Profile):
            curves = []
            points = []

            for curve in profile_loop:
                tessellated_points = curve.Tessellate()
                points.extend(tessellated_points)
                curves.append(curve)

            dict_item = {}
            dict_item["curves"] = curves
            dict_item["points"] = points 
            floor_input.append(dict_item)
        
        n = len(floor_input)

        #comparing every loop looking for parent loops
        for i, dict_item in enumerate(floor_input):
            for j, comparison_item in enumerate(floor_input):
                if i == j:
                    continue
                if point_in_polygon_points(dict_item["points"][0], comparison_item["points"]):
                    loop = []
                    loop.append(dict_item["curves"])
                    loop.append(comparison_item["curves"])
                    floor_output.append(loop)
                    break
                floor_output.append(dict_item["curves"])
        


        for sketch in floor_output: 
            cl = CurveLoop()
            for c in sketch:
                cl.Append(c)
            Floor.Create(
                doc,
                floor,
                floor.GetTypeId(),
                floor.LevelId
            )
        doc.Delete(floor.Id)
            
            

except OperationCanceledException:
    print("Selection cancelled.")

except Exception:
    traceback.print_exc()
