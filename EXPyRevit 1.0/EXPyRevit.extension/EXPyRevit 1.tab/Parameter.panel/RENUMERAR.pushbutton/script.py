# -*- coding: utf-8 -*-

from Autodesk.Revit.DB import Transaction, ViewSheet
from pyrevit import forms
import traceback

uidoc = __revit__.ActiveUIDocument
doc = uidoc.Document


def pick_sheets():
    sheets = []

    for element_id in uidoc.Selection.GetElementIds():
        element = doc.GetElement(element_id)

        if isinstance(element, ViewSheet):
            sheets.append(element)

    return sheets


try:
    sheets = pick_sheets()

    if not sheets:
        forms.alert("Please pre-select one or more sheets in the Project Browser.")
        raise Exception("No sheets selected.")

    starting_number = forms.ask_for_string(
        prompt="Número inicial",
        default="0001"
    )

    if not starting_number:
        raise Exception("Operation cancelled.")

    width = len(starting_number)

    t = Transaction(doc, "Renumber sheets")
    t.Start()

    for i, sheet in enumerate(sheets):
        sheet.SheetNumber = str(int(starting_number) + i).zfill(width)

    t.Commit()

except Exception:
    traceback.print_exc()