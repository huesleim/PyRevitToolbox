# -*- coding: utf-8 -*-
from Autodesk.Revit.Exceptions import OperationCanceledException
from Autodesk.Revit.DB import BuiltInCategory, Transaction, BuiltInParameter, SectionType, FilteredElementCollector, ElementId, ScheduleFieldType
import traceback

# Select elements and declare variables #
uidoc = __revit__.ActiveUIDocument
doc = uidoc.Document
schedule = doc.ActiveView
table = schedule.GetTableData()
body = table.GetSectionData(SectionType.Body)
elements = list(FilteredElementCollector(doc, schedule.Id).ToElements())

# Open transaction to modify the parameters #
t = Transaction(doc, 'Autofill IFC') 
t.Start()


# Set the schedule to not itemized #
definition = schedule.Definition
definition.IsItemized = False

# Set both ifc export parameters to empty string #
try:
    for i, elem in enumerate(elements):
        familyAndType = elem.get_Parameter(BuiltInParameter.ELEM_FAMILY_AND_TYPE_PARAM) 
        text = familyAndType.AsValueString() if familyAndType else ''
        value = ''

        firstParam = elem.get_Parameter(BuiltInParameter.IFC_EXPORT_ELEMENT_AS)
        if firstParam and not firstParam.IsReadOnly:
            firstParam.Set(value)

        secondParam = elem.get_Parameter(BuiltInParameter.IFC_EXPORT_PREDEFINEDTYPE)
        if secondParam and not secondParam.IsReadOnly:
            secondParam.Set(value)
    t.Commit()

# Rollback changes if the user cancels the operation or if an error occurs #
except OperationCanceledException:
    t.RollBack()

except Exception:
    t.RollBack()
    traceback.print_exc()