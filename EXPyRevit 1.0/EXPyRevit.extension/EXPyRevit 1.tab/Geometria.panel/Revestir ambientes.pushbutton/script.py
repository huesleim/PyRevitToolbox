# -*- coding: utf-8 -*-
"""Cria uma parede de revestimento ao lado de cada parede (e pilar) que
delimita os ambientes escolhidos, no modelo "parede cebola"."""
from Autodesk.Revit.DB import (
    BuiltInCategory,
    BuiltInParameter,
    CurveLoop,
    Element,
    FailureProcessingResult,
    FailureSeverity,
    FilteredElementCollector,
    IFailuresPreprocessor,
    JoinGeometryUtils,
    SpatialElementBoundaryLocation,
    SpatialElementBoundaryOptions,
    SpecTypeId,
    Transaction,
    Transform,
    UnitFormatUtils,
    Wall,
    WallKind,
    WallType,
    XYZ,
)
from Autodesk.Revit.DB.Architecture import Room
from pyrevit import forms, script

import helpers
from helpers import log, print_error

uidoc = __revit__.ActiveUIDocument
doc = uidoc.Document

# Futuramente vira uma opcao na interface
INCLUDE_COLUMNS = True
COLUMN_CATEGORIES = (
    int(BuiltInCategory.OST_Columns),
    int(BuiltInCategory.OST_StructuralColumns),
)
DEFAULT_HEIGHT_FT = 280 / 30.48  # 2,80 m


class SwallowWarnings(IFailuresPreprocessor):
    def PreprocessFailures(self, failures_accessor):
        for failure in failures_accessor.GetFailureMessages():
            if failure.GetSeverity() == FailureSeverity.Warning:
                failures_accessor.DeleteWarning(failure)
        return FailureProcessingResult.Continue


#### ENTRADAS ####

def room_label(room):
    number = room.Number or ""
    name_param = room.get_Parameter(BuiltInParameter.ROOM_NAME)
    name = name_param.AsString() if name_param else ""
    return "{} - {} - {}".format(room.Level.Name, number, name)


def pick_rooms():
    rooms = [
        r
        for r in FilteredElementCollector(doc)
        .OfCategory(BuiltInCategory.OST_Rooms)
        .WhereElementIsNotElementType()
        if isinstance(r, Room) and r.Area > 0
    ]
    rooms.sort(key=lambda r: (r.Level.ProjectElevation, r.Number or ""))
    label_to_room = {room_label(r): r for r in rooms}
    selected = forms.SelectFromList.show(
        [room_label(r) for r in rooms],
        title="Escolha os ambientes a revestir",
        multiselect=True,
    )
    return [label_to_room[label] for label in selected] if selected else []


def pick_wall_type():
    types = [
        wt
        for wt in FilteredElementCollector(doc).OfClass(WallType)
        if wt.Kind == WallKind.Basic
    ]
    name_to_type = {Element.Name.GetValue(wt): wt for wt in types}
    selected = forms.SelectFromList.show(
        sorted(name_to_type.keys()),
        title="Escolha o tipo de parede de revestimento",
        multiselect=False,
    )
    return name_to_type.get(selected) if selected else None


def format_length(value):
    return UnitFormatUtils.Format(doc.GetUnits(), SpecTypeId.Length, value, True)


def parse_length(text):
    result = UnitFormatUtils.TryParse(doc.GetUnits(), SpecTypeId.Length, text)
    if isinstance(result, tuple):
        return result[1] if result[0] else None
    return None


def ask_length(prompt, default_value, allow_zero):
    while True:
        typed = forms.ask_for_string(prompt=prompt, default=format_length(default_value))
        if typed is None:
            return None
        value = parse_length(typed)
        if value is not None and (value > 0 or (allow_zero and value >= 0)):
            return value
        forms.alert("Valor inválido: '{}'. Use as unidades do projeto.".format(typed))


#### GEOMETRIA ####

def is_cladding_host(element):
    if isinstance(element, Wall):
        return element.WallType.Kind != WallKind.Curtain
    if INCLUDE_COLUMNS and element is not None and element.Category is not None:
        return element.Category.Id.IntegerValue in COLUMN_CATEGORIES
    return False


def flatten_to(curve, z):
    start = curve.GetEndPoint(0)
    return curve.CreateTransformed(Transform.CreateTranslation(XYZ(0, 0, z - start.Z)))


def midpoint(curve):
    return curve.Evaluate(0.5, True)


def offset_is_inside(curve, room, z_test):
    mid = midpoint(curve)
    return room.IsPointInRoom(XYZ(mid.X, mid.Y, z_test))


def offset_whole_loop(curves, distance, room, z_test):
    """Offset do loop inteiro (cantos se encontram). None se nao der."""
    try:
        loop = CurveLoop()
        for c in curves:
            loop.Append(c)
    except Exception:
        return None
    for signed in (distance, -distance):
        try:
            result = list(CurveLoop.CreateViaOffset(loop, signed, XYZ.BasisZ))
        except Exception:
            continue
        if len(result) != len(curves):
            continue
        longest = max(range(len(result)), key=lambda i: result[i].Length)
        if offset_is_inside(result[longest], room, z_test):
            return result
    return None


def offset_each_curve(curves, distance, room, z_test):
    """Plano B: offset segmento a segmento (cantos sem acabamento)."""
    result = []
    for c in curves:
        chosen = None
        for signed in (distance, -distance):
            try:
                candidate = c.CreateOffset(signed, XYZ.BasisZ)
            except Exception:
                continue
            if offset_is_inside(candidate, room, z_test):
                chosen = candidate
                break
        result.append(chosen)
    return result


def room_side_normal(original, offset):
    """Direcao horizontal que aponta da parede hospedeira para o ambiente."""
    tangent = offset.ComputeDerivatives(0.5, True).BasisX.Normalize()
    normal = XYZ.BasisZ.CrossProduct(tangent).Normalize()
    shift = midpoint(offset) - midpoint(original)
    return normal if normal.DotProduct(shift) >= 0 else normal.Negate()


#### CRIACAO ####

def clad_room(room, wall_type, base_offset, height, summary):
    options = SpatialElementBoundaryOptions()
    options.SpatialElementBoundaryLocation = SpatialElementBoundaryLocation.Finish
    level_z = room.Level.ProjectElevation
    z_test = room.get_BoundingBox(None).Min.Z + 0.5
    distance = wall_type.Width / 2.0
    label = room_label(room)

    for segments in room.GetBoundarySegments(options):
        curves = [flatten_to(s.GetCurve(), level_z) for s in segments]
        hosts = [doc.GetElement(s.ElementId) for s in segments]

        offsets = offset_whole_loop(curves, distance, room, z_test)
        if offsets is None:
            log("  [{}] Loop sem offset continuo, usando segmento a segmento".format(label))
            offsets = offset_each_curve(curves, distance, room, z_test)

        for original, offset, host in zip(curves, offsets, hosts):
            if not is_cladding_host(host):
                summary["skipped"] += 1
                continue
            if offset is None or offset.Length < doc.Application.ShortCurveTolerance:
                summary["failed"] += 1
                continue
            try:
                wall = Wall.Create(
                    doc, offset, wall_type.Id, room.LevelId,
                    height, base_offset, False, False,
                )
                if wall.Orientation.DotProduct(room_side_normal(original, offset)) < 0:
                    wall.Flip()
                try:
                    JoinGeometryUtils.JoinGeometry(doc, wall, host)
                except Exception:
                    pass
                summary["created"] += 1
            except Exception:
                summary["failed"] += 1
                print_error("Falha ao criar revestimento em {}".format(label))


#### MAIN ####

rooms = pick_rooms()
if not rooms:
    forms.alert("Nenhum ambiente selecionado.", exitscript=True)

wall_type = pick_wall_type()
if wall_type is None:
    forms.alert("Nenhum tipo de parede selecionado.", exitscript=True)

base_offset = ask_length("Altura inicial / deslocamento da base (unidades do projeto)", 0.0, True)
if base_offset is None:
    script.exit()

height = ask_length("Altura da parede (unidades do projeto)", DEFAULT_HEIGHT_FT, False)
if height is None:
    script.exit()

summary = {"created": 0, "skipped": 0, "failed": 0}
t = Transaction(doc, "Revestir ambientes")
options = t.GetFailureHandlingOptions()
options.SetFailuresPreprocessor(SwallowWarnings())
t.SetFailureHandlingOptions(options)

try:
    t.Start()
    for room in rooms:
        clad_room(room, wall_type, base_offset, height, summary)
    t.Commit()
    log(
        "{} paredes criadas | {} segmentos ignorados (sem parede/pilar) | {} falhas".format(
            summary["created"], summary["skipped"], summary["failed"]
        )
    )
except Exception:
    if t.HasStarted() and not t.HasEnded():
        t.RollBack()
    print_error("Falha geral no script")
