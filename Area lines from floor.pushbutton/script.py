# -*- coding: utf-8 -*-

from Autodesk.Revit.UI.Selection import ObjectType, ISelectionFilter
from Autodesk.Revit.Exceptions import OperationCanceledException
from Autodesk.Revit.DB import BuiltInCategory, Transaction
from pyrevit import script
import traceback


class FloorSelectionFilter(ISelectionFilter):
    def AllowElement(self, element):
        return (
            element.Category
            and element.Category.Id.IntegerValue == int(BuiltInCategory.OST_Floors)
        )

    def AllowReference(self, reference, point):
        return False


##Select current UI and file 
uidoc = __revit__.ActiveUIDocument 
doc = uidoc.Document 


try:
    #Catches current view's plan, checks whether view is Area Plan Type and throws error if not.
    plan = uidoc.ActiveView
    if plan.ViewType != plan.ViewType.AreaPlan:
        print("Please switch to an Area Plan.")
        script.exit()
    

    #Prompts user to select objects and throws error if object is not a floor
    refs = uidoc.Selection.PickObjects(
        ObjectType.Element,
        FloorSelectionFilter(),
        "Select one or more floors"
    )


    #Loops every selected floor and creates area lines for each one
    t = Transaction(doc, "Create Lines")
    t.Start()

    for ref in refs:
        floor = doc.GetElement(ref.ElementId)

        #Defines parameters for NewAreaBoundaryLine function
        sketch = doc.GetElement(floor.SketchId)
        plane = sketch.SketchPlane


        #Loops every profile in floor and creates area lines for each one 
        for profileLoop in sketch.Profile:
            print("Creating lines")

            for curve in profileLoop:
                doc.Create.NewAreaBoundaryLine(
                    plane,
                    curve,
                    plan,
                )

    t.Commit()

    print("Na Victa é assim! :p")


except OperationCanceledException:
    print("Selection cancelled.")


except Exception:
    traceback.print_exc()