from Autodesk.Revit.DB import Transaction, FilteredElementCollector, SpotElevationType, BuiltInCategory
from pyrevit import forms
import traceback

uidoc = __revit__.ActiveUIDocument
doc = __revit__.ActiveUIDocument.Document
currentview = doc.ActiveView

def calc_area(points):
    n = len(points)
    area = 0.0
    for i in range(n):
        x0, y0 = points[i].X, points[i].Y
        x1, y1 = points[(i+1) % n].X, points[(i+1) % n].Y
        area += (x0 * y1) - (x1 * y0)
    return abs(area) / 2

def process_rooms(rooms):
    processed_rooms = []
    for room in rooms:
        opt = SpatialElementBoundaryOptions()
        opt.SpatialElementBoundaryLocation = SpatialElementBoundaryLocation.Finish
        polygon_list = room.GetBoundarySegments(opt)
        polygon_result = {}
        for polygon in polygon_list:
            polygon_points = []
            for id, segment in enumerate(polygon):
                curve = segment.GetCurve()
                points = curve.Tessellate()
                polygon_points.extend(points)
                polygon_result[id]["points"] = points
                polygon_result[id]["area"] = calc_area(points)

        biggest_polygon_id = max(polygon_result, key = lambda k: polygon_result[k]["area"])
        processed_rooms.append({
            "id": room.Id,
            "room": room,
            "biggest_polygon": polygon_result[biggest_polygon_id]
        })
    return processed_rooms

def check_if_inside(point, polygon_points):
    x, y = point.X, point.Y
    n = len(polygon_points)
    inside = False

    for l in range(n):
        x0, y0 = polygon_points[l].X, polygon_points[l].Y
        x1, y1 = polygon_points[(l+1) % n].X, polygon_points[(l+1) % n].Y

        intersects = ((y0 > y) != (y1 > y)) and (
            x < (x1 - x0) * (y - y0) / (y1 - y0) + x0
        )

        if intersects:
            inside = not inside
        
    return inside

def check_unnoted_rooms(rooms, existing_elevations):
    unnoted_rooms = {}
    for room in rooms:
        room_polygon = room["biggest_polygon"]["points"]
        for elevation in existing_elevations:
            if check_if_inside(elevation.Origin, room_polygon):
                unnoted_rooms[room["id"]] = room
    return unnoted_rooms

#1 Escolher família 
elevation_types = FilteredElementCollector(doc).OfClass(SpotDimensionType).ToElements()
selected_type = forms.SelectFromList.show(elevation_types)

#2 Coletar todos os ambientes visíveis na vista
rooms = FilteredElementCollector(doc, currentview.Id).OfCategory(BuiltInCategory.OST_Rooms).WhereElementIsNotElementType().ToElements()


#3 Checar em quais ambientes o ponto de elevação está presente
rooms_boundaries = {}

existing_elevations = FilteredElementCollector (doc, currentview.Id).OfCategory(BuiltInCategory.OST_SpotElevations).WhereElementIsNotElementType().ToElements()
for elevation in existing_elevations:
    rooms [:] = [room for room in rooms if not point_in_polygon(elevation, rooms_boundaries[room.Id])]


#4 Checar se há room tag

# Locar a cota, considerando se há room tag

