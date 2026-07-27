from Autodesk.Revit.DB import FilteredElementCollector, RevitLinkType, Element
import traceback

uidoc = __revit__.ActiveUIDocument
doc = uidoc.Document

links = FilteredElementCollector(doc).OfClass(RevitLinkType).ToElements()

for link in links:
    name = Element.Name.GetValue(link)

    try:
        result = link.Unload(None)

    except Exception:
        traceback.print_exc()
