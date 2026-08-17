# -*- coding: utf-8 -*-
import traceback
from pyrevit import forms
from Autodesk.Revit.DB import (
    BuiltInCategory,
    Element,
    ElementCategoryFilter,
    FilteredElementCollector,
    FindReferenceTarget,
    LinkElementId,
    ReferenceIntersector,
    RevitLinkInstance,
    SpotDimensionType,
    Transaction,
    UV,
    View3D,
    ViewFamily,
    ViewFamilyType,
    ViewType,
    XYZ
)
def get_tags_and_links(doc):
    tags = FilteredElementCollector(doc, current_view.Id)
    .OfCategory(BuiltInCategory.OST_RoomTags)
    .WhereElementIsNotElementType()
    .ToElements()

    links = FilteredElementCollector(doc)
    .OfClass(RevitLinkInstance)
    .ToElements()
    if not links:
        raise Exception("Nenhum link carregado no modelo.")

    return tags, links

def process_tags(tags, links):
    orphaned_tags = {}
    for tag in tags:
        if tag.IsOrphaned:
            orphaned_tags[tag] = {}
            orphaned_tags[tag]["isLinked"] = tag.TaggedRoomId
            orphaned_tags[tag]["id"] = tag.Id
            if not orphaned_tags[tag]["isLinked"]: 
                orphaned_tags[tag]["location"] = tag.Location.Point
                orphaned_tags[tag]["room_id"] = tag.TaggedLocalRoomId
            else: 
                for link in links:
                    link_doc = link.GetLinkDocument()

                    inverse_transform = link.GetTotalTransform().Inverse
                    point_in_link = inverse_transform.OfPoint(tag.Location.Point)
                    for phase in link_doc.Phases:
                        room = link_doc.GetRoomAtPoint(point_in_link, phase)
                        if room:
                            orphaned_tags[tag]["location"] = point_in_link
                            orphaned_tags[tag]["room_id"] = tag.TaggedRoomId
                            break
                            
    return orphaned_tags

def tag_rooms(orphaned_tags):
    for tag in orphaned_tags:
        link_element_id = LinkElementId(tag["isLinked"], tag["room_id"])
        uv_point = UV(tag["location"].X, tag["location"].Y)
        newTag = doc.Create.NewRoomTag(
        link_element_id,
        uvPoint,
        current_view.Id
    )

uidoc = __revit__.ActiveUIDocument
doc = uidoc.Document 
current_view = uidoc.doc.ActiveView
if current_view.ViewType != ViewType.FloorPlan:
    forms.alert("Selecione uma planta de piso!", exitscript=True)
t = Transaction(doc, "Corrigir tags órfãs")

try: 
    t.Start()
    tags, links = get_tags_and_links()
    tag_rooms(process_tags(tags, links))
    t.Commit()
except Exception:
    traceback.print_exc

