# -*- coding: utf-8 -*-
from Autodesk.Revit.UI.Selection import ObjectType
from Autodesk.Revit.Exceptions import OperationCanceledException
from Autodesk.Revit.DB import Floor, CurveLoop, BuiltInCategory, Transaction
from pyrevit import script


uidoc = __revit__.ActiveUIDocument
doc = uidoc.Document

try:
    ref = uidoc.Selection.PickObject(ObjectType.Element, "Pick a floor")
    floor = doc.GetElement(ref.ElementId)

    if floor.Category.Id.Value != int(BuiltInCategory.OST_Floors):
        print("Not a floor!")
        script.exit()

    sketch = doc.GetElement(floor.SketchId)

    t = Transaction(doc, "Separate Floor")
    t.Start()

    for profileLoop in sketch.Profile:
        print("Separating one floor")

        cl = CurveLoop()

        for c in profileLoop:
            cl.Append(c)

        Floor.Create(
            doc,
            [cl],
            floor.GetTypeId(),
            floor.LevelId
        )
    doc.Delete(floor.Id)

    t.Commit()
    print("Na Victa é assim! :p")

except OperationCanceledException:
    print("Selection cancelled.")

except Exception:
    traceback.print_exc()