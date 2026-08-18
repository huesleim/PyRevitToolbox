# -*- coding: utf-8 -*-
import traceback
from pyrevit import forms
from Autodesk.Revit.DB import (
    BuiltInCategory,
    Element,
    ElementCategoryFilter,
    FilteredElementCollector,
    FindReferenceTarget,
    ReferenceIntersector,
    SpotDimensionType,
    Transaction,
    View3D,
    ViewFamily,
    ViewFamilyType,
    XYZ,
)


def resolve_helper_view(doc):
    view_types = FilteredElementCollector(doc).OfClass(ViewFamilyType).ToElements()
    view3d_type = next(
        vt for vt in view_types if vt.ViewFamily == ViewFamily.ThreeDimensional
    )
    helper_view = View3D.CreateIsometric(doc, view3d_type.Id)
    doc.Regenerate()
    return helper_view

def resolve_tagged_rooms(existing_room_tags):
    tags_data = {}
    for tag in existing_room_tags:
        if tag.IsOrphaned:
            print("Tag órfã")
            continue

        if tag.IsTaggingLink:
            link_elem_id = tag.TaggedRoomId
            link_instance = doc.GetElement(link_elem_id.LinkInstanceId)
            link_doc = link_instance.GetLinkDocument()
            room = link_doc.GetElement(link_elem_id.LinkedElementId)
        else:
            room = tag.Room

        if room is None:
            print("Tag sem ambiente hospedeiro")
            continue

        if not tag.IsInRoom:
            print("Tag fora do ambiente hospedeiro")
            continue

        if room.Location is None or room.Area == 0:
            print("Ambiente aberto")
            continue

        room_name = Element.Name.GetValue(room)
        print("Encontrada tag para", room_name)

        tags_data[tag] = {}
        tags_data[tag]["room"] = room_name
        tags_data[tag]["location"] = tag.Location.Point
        tags_data[tag]["ray_location"] = XYZ(
            tag.Location.Point.X, tag.Location.Point.Y, tag.Location.Point.Z + 3
        )

    return tags_data

def resolve_y_coordinate(tags_data):
    tag = next(iter(tags_data))
    bbox = tag.get_BoundingBox(currentview)
    tag_height = abs(bbox.Max.Y - bbox.Min.Y)
    offset = tag_height/5
    print("offset:", offset)
    return offset


def resolve_reference(tags_data, helper_view):
    filter = ElementCategoryFilter(BuiltInCategory.OST_Floors)
    intersector = ReferenceIntersector(filter, FindReferenceTarget.Face, helper_view)
    intersector.FindReferencesInRevitLinks = True

    for tag_data in tags_data.values():
        direction = XYZ(0, 0, -1)
        print("Procurando piso imediatamente abaixo para ambiente", tag_data["room"])

        intersections = intersector.Find(tag_data["ray_location"], direction)

        if intersections:
            print("Intersections:", len(intersections))

            for i, intersection in enumerate(intersections):
                reference = intersection.GetReference()

                print(
                    "  [{}] ElementId={} LinkedElementId={} Proximity={}".format( 
                        i,
                        reference.ElementId.IntegerValue,
                        reference.LinkedElementId.IntegerValue,
                        intersection.Proximity,
                    )
                )
            closest_face = min(intersections, key=lambda intersection: intersection.Proximity)
            reference = closest_face.GetReference()
            tag_data["reference"] = reference
            
            ####review this
            tag_data["reference_point"] = reference.GlobalPoint

            tag_point = tag_data["location"]
            reference_point = reference.GlobalPoint

            delta = tag_point - reference_point

            vertical_distance = delta.DotProduct(currentview.UpDirection)

            aligned_point = (
                reference_point
                + currentview.UpDirection * vertical_distance
            )

            offset = resolve_y_coordinate(tags_data)

            tag_data["spot_placement"] = (
                aligned_point
                - currentview.UpDirection * offset
            )

    doc.Delete(helper_view.Id)
    return tags_data


def create_elevations(tags_data):
    for tag_data in tags_data.values():
        print("Criando tag para o ambiente", (tag_data["room"]))

        if "reference" not in tag_data:
            print("Nenhuma referência de piso encontrada para o ambiente", (tag_data["room"]))
            continue

        try:
            reference_point = tag_data["spot_placement"]

            spot_elevation = doc.Create.NewSpotElevation(
                currentview,
                tag_data["reference"],
                reference_point,
                reference_point,
                reference_point,
                reference_point,
                hasLeader=False,
            )

            spot_elevation.ChangeTypeId(selected_type.Id)
        except Exception:
            print("Não foi possível criar cota para:", tag_data["room"])
            traceback.print_exc()
            continue


print("Início do script")
uidoc = __revit__.ActiveUIDocument
doc = __revit__.ActiveUIDocument.Document
currentview = doc.ActiveView
t = Transaction(doc, "Colocar elevações de ponto")

# Prompt user to select spotdimensiontype
try:
    print("Vista atual:", currentview.Name)
    elevation_types = (
        FilteredElementCollector(doc).OfClass(SpotDimensionType).ToElements()
    )
    name_to_type = {Element.Name.GetValue(t): t for t in elevation_types}
    selected_name = forms.SelectFromList.show(list(name_to_type.keys()))
    print("Tipo selecionado:", selected_name)

    if not selected_name:
        forms.alert("Nenhum tipo de elevação de ponto selecionado.", exitscript=True)

    selected_type = name_to_type[selected_name]
    print("Tipo selecionado:", selected_type)

    existing_room_tags = (
        FilteredElementCollector(doc, currentview.Id)
        .OfCategory(BuiltInCategory.OST_RoomTags)
        .WhereElementIsNotElementType()
        .ToElements()
    )

    t.Start()

    helper_view = resolve_helper_view(doc)
    tags_data = resolve_tagged_rooms(existing_room_tags)
    tags_data = resolve_reference(tags_data, helper_view)
    create_elevations(tags_data)

    print("Operação concluída")
    t.Commit()

except Exception:
    traceback.print_exc()
    t.RollBack()
