import traceback
from pyrevit import forms
from Autodesk.Revit.DB import (
    BuiltInCategory,
    Element,
    ElementCategoryFilter,
    FilteredElementCollector,
    FindReferenceTarget,
    ReferenceIntersector,
    SpatialElementBoundaryLocation,
    SpatialElementBoundaryOptions,
    SpotDimensionType,
    Transaction,
    View3D,
    ViewFamily,
    ViewFamilyType,
    XYZ
)

class elementListItem(forms.TemplateListItem):
    @property
    def name(self):
        return Element.Name.GetValue(self.item)



def calc_area(points):
    n = len(points)
    area = 0.0
    for i in range(n):
        x0, y0 = points[i].X, points[i].Y
        x1, y1 = points[(i + 1) % n].X, points[(i + 1) % n].Y
        area += (x0 * y1) - (x1 * y0)
    return abs(area) / 2


def process_rooms(rooms):
    processed_rooms = {}
    for room in rooms:
        opt = SpatialElementBoundaryOptions()
        opt.SpatialElementBoundaryLocation = SpatialElementBoundaryLocation.Finish
        polygon_list = room.GetBoundarySegments(opt)
        polygon_result = {}
        for index, polygon in enumerate(polygon_list):
            polygon_points = []
            for segment in polygon:
                curve = segment.GetCurve()
                points = curve.Tessellate()
                polygon_points.extend(points)
            polygon_result[index] = {
                "polygon": polygon,
                "points": polygon_points,
                "area": calc_area(polygon_points),
            }
        biggest_polygon_id = max(
            polygon_result, key=lambda k: polygon_result[k]["area"]
        )
        processed_rooms[room.Id] = {
            "room": room,
            "biggest_polygon": polygon_result[biggest_polygon_id]["polygon"],
            "points": polygon_result[biggest_polygon_id]["points"],
        }
    return processed_rooms


def check_if_inside(point, polygon_points):
    x, y = point.X, point.Y
    n = len(polygon_points)
    inside = False
    for l in range(n):
        x0, y0 = polygon_points[l].X, polygon_points[l].Y
        x1, y1 = polygon_points[(l + 1) % n].X, polygon_points[(l + 1) % n].Y

        intersects = ((y0 > y) != (y1 > y)) and (
            x < (x1 - x0) * (y - y0) / (y1 - y0) + x0
        )

        if intersects:
            inside = not inside

    return inside


def check_unnoted_rooms(processed_rooms, existing_elevations):
    unnoted_rooms = {}
    for room_id, room_data in processed_rooms.items():
        for elevation in existing_elevations:
            if check_if_inside(elevation.Origin, room_data["points"]):
                break
        else:
            unnoted_rooms[room_id] = room_data
    return unnoted_rooms


def check_untagged_rooms(unnoted_rooms, existing_tags):
    tagged_ids = {}
    for tag in existing_tags:
        tagged_ids[tag.Room.Id] = tag
    for room_id, room_data in unnoted_rooms.items():
        if room_id in tagged_ids:
            room_data["tagged"] = tagged_ids[room_id]
        else:
            room_data["tagged"] = None
    return unnoted_rooms


def resolve_origin(unnoted_rooms):
    for room_id, room_data in unnoted_rooms.items():
        if not room_data["tagged"]:
            room_data["origin"] = room_data["room"].Location.Point
        else:
            tag = room_data["tagged"]
            tag_location = tag.Location.Point
            x, y, z = tag_location.X, tag_location.Y, tag_location.Z
            new_origin = XYZ(x, y + 1, z)
            room_data["origin"] = new_origin
    return unnoted_rooms


def resolve_reference(unnoted_rooms):
    view_types = FilteredElementCollector(doc).OfClass(ViewFamilyType).ToElements()
    view3d_type = next(
        vt for vt in view_types if vt.ViewFamily == ViewFamily.ThreeDimensional
    )
    helper_view = View3D.CreateIsometric(doc, view3d_type.Id)
    filter = ElementCategoryFilter(BuiltInCategory.OST_Floors)
    intersector = ReferenceIntersector(filter, FindReferenceTarget.Face, helper_view)
    for room_data in unnoted_rooms.values():
        direction = XYZ(0, 0, -1)
        intersections = intersector.Find(room_data["origin"], direction)
        if intersections:
            room_data["reference"] = intersections[0].GetReference()
    doc.Delete(helper_view.Id)
    return unnoted_rooms


def create_elevations(unnoted_rooms):
    for room_data in unnoted_rooms.values():
        print("Creating elevation for room:", Element.Name.GetValue(room_data["room"]))
        if "reference" not in room_data:
            print("No reference found for room:", Element.Name.GetValue(room_data["room"]))
            continue
        else: 
            spot_elevation = doc.Create.NewSpotElevation(
                currentview,
                room_data["reference"],
                room_data["origin"],
                room_data["origin"],
                room_data["origin"],
                room_data["origin"],
                hasLeader=False,
            )
            spot_elevation.ChangeTypeId(selected_type.Id)


print("START")
uidoc = __revit__.ActiveUIDocument
doc = __revit__.ActiveUIDocument.Document
currentview = doc.ActiveView
t = Transaction(doc, "Place Elevations")


##REVIEW THIS
try:
    elevation_types = FilteredElementCollector(doc).OfClass(SpotDimensionType).ToElements()
    name_to_type = {Element.Name.GetValue(t): t for t in elevation_types}
    selected_name = forms.SelectFromList.show(list(name_to_type.keys()))
    print("Selected type:", selected_name)
    if not selected_name:
        forms.alert("No type selected.", exitscript=True)
    selected_type = name_to_type[selected_name]
    print("Selected type:", selected_type)
except Exception:
    traceback.print_exc()

rooms = (
    FilteredElementCollector(doc, currentview.Id)
    .OfCategory(BuiltInCategory.OST_Rooms)
    .WhereElementIsNotElementType()
    .ToElements()
)
print("Rooms found:", len(rooms))

existing_elevations = (
    FilteredElementCollector(doc, currentview.Id)
    .OfCategory(BuiltInCategory.OST_SpotElevations)
    .WhereElementIsNotElementType()
    .ToElements()
)
print("Existing elevations found:", len(existing_elevations))

existing_tags = (
    FilteredElementCollector(doc, currentview.Id)
    .OfCategory(BuiltInCategory.OST_RoomTags)
    .WhereElementIsNotElementType()
    .ToElements()
)
print("Existing tags found:", len(existing_tags))

try:
    t.Start()
    room_data = resolve_reference(
        resolve_origin(
            check_untagged_rooms(
                check_unnoted_rooms(process_rooms(rooms), existing_elevations),
                existing_tags,
            )
        )
    )
    create_elevations(room_data)
    t.Commit()

except Exception:
    traceback.print_exc()