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
        forms.alert("Antes de rodar o script, selecione as pranchas que deseja renumerar")
        raise Exception("Nenhuma prancha selecionada")
    starting_number = forms.ask_for_string(
        prompt="Número inicial.",
        default="0001"
    )
    if not starting_number:
        raise Exception("Operação cancelada")

    
    starting_number_int = []
    for character in starting_number:
        if character.isdigit():
            starting_number_int.append(character)

    starting_number = "".join(starting_number_int)
    if not starting_number:
        forms.alert("O número inicial deve conter ao menos um dígito.")
        raise Exception("Número inválido")
    
    t = Transaction(doc, "Renumber sheets")
    t.Start()

    for i, sheet in enumerate(sheets):
        sheet.SheetNumber = str(int(starting_number) + i).zfill(len(starting_number))

    t.Commit()

except Exception:
    traceback.print_exc()