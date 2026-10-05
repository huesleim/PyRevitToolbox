# -*- coding: utf-8 -*-
import traceback
from pyrevit import forms
from Autodesk.Revit.DB import (
    BuiltInCategory,
    ElementId,
    FilteredElementCollector,
    LinkElementId,
    RevitLinkInstance,
    Transaction,
    UV,
    ViewType,
)


def get_tags_and_links(doc):
    tags = (
        FilteredElementCollector(doc, current_view.Id)
        .OfCategory(BuiltInCategory.OST_RoomTags)
        .WhereElementIsNotElementType()
        .ToElements()
    )

    links = FilteredElementCollector(doc).OfClass(RevitLinkInstance).ToElements()
    if not links:
        raise Exception("Nenhum link carregado no modelo.")

    return tags, links


def find_room_at_point(target_doc, point):
    for phase in target_doc.Phases:
        room = target_doc.GetRoomAtPoint(point, phase)
        if room:
            return room
    return None


def get_tagged_room_info(tag):
    try:
        local_id = tag.TaggedLocalRoomId
        if local_id != ElementId.InvalidElementId:
            return True, None
    except SystemError:
        pass

    try:
        tagged_room_id = tag.TaggedRoomId
        if tagged_room_id.LinkInstanceId != ElementId.InvalidElementId:
            return False, tagged_room_id.LinkInstanceId
    except SystemError:
        pass

    return None, None


def process_tags(tags, links):
    orphaned_tags = {}
    failed_tags = []

    for tag in tags:
        if not tag.IsOrphaned:
            continue

        is_local, link_instance_id = get_tagged_room_info(tag)

        if is_local is None:
            failed_tags.append(tag)
            continue

        info = {"id": tag.Id, "is_local": is_local}

        if is_local:
            point = tag.Location.Point
            room = find_room_at_point(doc, point)
            if room:
                info["location"] = point
                info["room_id"] = room.Id
                orphaned_tags[tag] = info
            else:
                failed_tags.append(tag)
        else:
            link = next((l for l in links if l.Id == link_instance_id), None)
            if link is None:
                failed_tags.append(tag)
                continue

            link_doc = link.GetLinkDocument()
            point = link.GetTotalTransform().Inverse.OfPoint(tag.Location.Point)
            room = find_room_at_point(link_doc, point)

            if room:
                info["location"] = point
                info["room_id"] = room.Id
                info["link_instance_id"] = link.Id
                orphaned_tags[tag] = info
            else:
                failed_tags.append(tag)

    return orphaned_tags, failed_tags


def tag_rooms(orphaned_tags):
    for tag_info in orphaned_tags.values():
        if tag_info["is_local"]:
            link_element_id = LinkElementId(tag_info["room_id"])
        else:
            link_element_id = LinkElementId(
                tag_info["link_instance_id"], tag_info["room_id"]
            )

        uv_point = UV(tag_info["location"].X, tag_info["location"].Y)

        doc.Create.NewRoomTag(link_element_id, uv_point, current_view.Id)


uidoc = __revit__.ActiveUIDocument
doc = uidoc.Document
current_view = uidoc.ActiveView

if current_view.ViewType != ViewType.FloorPlan:
    forms.alert("Selecione uma planta de piso!", exitscript=True)

t = Transaction(doc, "Corrigir tags órfãs")

try:
    t.Start()
    tags, links = get_tags_and_links(doc)
    orphaned_tags, failed_tags = process_tags(tags, links)
    tag_rooms(orphaned_tags)
    t.Commit()

    msg = "{} tag(s) corrigida(s).".format(len(orphaned_tags))
    if failed_tags:
        msg += "\n{} tag(s) nao puderam ser recuperadas (room provavelmente deletada).".format(
            len(failed_tags)
        )
    forms.alert(msg)

except Exception:
    t.RollBack()
    traceback.print_exc()
