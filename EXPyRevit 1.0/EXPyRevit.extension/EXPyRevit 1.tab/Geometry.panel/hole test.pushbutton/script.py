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
            points_list.append(tessellated_points)
        
        curve_array_dict["points"] = points_list
        curve_array_objects_dict[i] = curve_array_dict
    
    return curve_array_objects_dict

def search_cache(point_array, curve_array_objects_dict):



def point_in_polygon_points(curve_array_objects_dict):
    for i, element in enumerate(curve_array_objects_dict):
        for j, other_element in enumerate(curve_array_objects_dict):
            if i == j: 
                continue
            
            x, y = element[i]["points"][0].X, element[i]["points"][0].Y
            

            inside = False
            n = len(curve_array_objects_dict[j]["points"])
            k = n-1

            for l in range(n):
                xk, yk = element[l]["points"][0].X, element[l]["points"][0].Y
                xk, yk = polygon_points[k].X, polygon_points[k].Y
                xj, yj = polygon_points[l].X, polygon_points[l].Y
                intersects = ((yi > y) != (yj > y)) and (
                    x < (xj - xi) * (y - yi) / (yj - yi) + xi
                )

                if intersects:
                    inside = not inside

                j = i

            return inside


def create_floors



# curve_output = []

# try: 
    
#     floor = pick_floor()
#     if floor:
#         floor_type_id = floor.GetTypeId()
#         floor_level_id = floor.LevelId
#         sketch = doc.GetElement(floor.SketchId)

#         floor_input = []
#         floor_output = []
#         inside = False

#         #populating floor_input with curves and points
#         for loop_index, profile_loop in enumerate(sketch.Profile):
#             curves = []
#             points = []

#             for curve in profile_loop:
#                 tessellated_points = curve.Tessellate()
#                 points.extend(tessellated_points)
#                 curves.append(curve)

#             dict_item = {}
#             dict_item["curves"] = curves
#             dict_item["points"] = points 
#             floor_input.append(dict_item)
        
#         n = len(floor_input)

#         #comparing every loop looking for parent loops
#         for i, dict_item in enumerate(floor_input):
#             for j, comparison_item in enumerate(floor_input):
#                 if i == j:
#                     continue
#                 if point_in_polygon_points(dict_item["points"][0], comparison_item["points"]):
#                     loop = []
#                     loop.append(dict_item["curves"])
#                     loop.append(comparison_item["curves"])
#                     floor_output.append(loop)
#                     break
#                 floor_output.append(dict_item["curves"])
        


#         for sketch in floor_output: 
#             cl = CurveLoop()
#             for c in sketch:
#                 cl.Append(c)
#             Floor.Create(
#                 doc,
#                 floor,
#                 floor.GetTypeId(),
#                 floor.LevelId
#             )
#         doc.Delete(floor.Id)
            
            

except OperationCanceledException:
    print("Selection cancelled.")

except Exception:
    traceback.print_exc()
