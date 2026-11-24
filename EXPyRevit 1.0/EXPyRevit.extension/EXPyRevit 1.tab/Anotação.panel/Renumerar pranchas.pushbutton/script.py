# -*- coding: utf-8 -*-
import re

from Autodesk.Revit.DB import Element, FilteredElementCollector, Transaction, ViewSheet
from pyrevit import forms, script

import helpers

uidoc = __revit__.ActiveUIDocument
doc = uidoc.Document

MAX_PREVIEW = 25


def natural_key(text):
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", text)]


def sheet_label(sheet):
    return "{} - {}".format(sheet.SheetNumber, Element.Name.GetValue(sheet))


def pick_sheets(all_sheets):
    ordered = sorted(all_sheets, key=lambda s: natural_key(s.SheetNumber))
    label_to_sheet = {sheet_label(s): s for s in ordered}
    selected = forms.SelectFromList.show(
        [sheet_label(s) for s in ordered],
        title="Escolha as pranchas a serem renumeradas",
        multiselect=True,
    )
    if not selected:
        return []
    sheets = [label_to_sheet[label] for label in selected]
    return sorted(sheets, key=lambda s: natural_key(s.SheetNumber))


def ask_starting_number():
    """Retorna apenas os dígitos digitados, None se cancelado."""
    while True:
        typed = forms.ask_for_string(prompt="Número inicial.", default="0001")
        if not typed:
            return None
        digits = "".join(c for c in typed if c.isdigit())
        if digits:
            return digits
        forms.alert("O número inicial deve conter ao menos um dígito.")


def build_targets(sheets, starting_number):
    width = len(starting_number)
    start = int(starting_number)
    return [str(start + i).zfill(width) for i in range(len(sheets))]


def find_conflicts(targets, sheets, all_sheets):
    """Pranchas fora da seleção que já usam algum número de destino."""
    selected_ids = set(s.Id for s in sheets)
    taken = {s.SheetNumber: s for s in all_sheets if s.Id not in selected_ids}
    return [taken[n] for n in targets if n in taken]


def preview_text(sheets, targets):
    lines = ["{}  ->  {}".format(s.SheetNumber, n) for s, n in zip(sheets, targets)]
    if len(lines) > MAX_PREVIEW:
        hidden = len(lines) - MAX_PREVIEW
        lines = lines[:MAX_PREVIEW] + ["... (+{} pranchas)".format(hidden)]
    return "\n".join(lines)


def renumber(sheets, targets):
    t = Transaction(doc, "Renumerar pranchas")
    t.Start()
    try:
        # 1a passada: números temporários liberam os números atuais da seleção
        for sheet in sheets:
            sheet.SheetNumber = "TMP-{}".format(sheet.Id)
        # 2a passada: números finais
        for sheet, number in zip(sheets, targets):
            sheet.SheetNumber = number
        t.Commit()
    except Exception:
        t.RollBack()
        raise


all_sheets = list(FilteredElementCollector(doc).OfClass(ViewSheet).ToElements())
sheets = pick_sheets(all_sheets)
if not sheets:
    forms.alert("Nenhuma prancha selecionada.", exitscript=True)

while True:
    starting_number = ask_starting_number()
    if starting_number is None:
        script.exit()

    targets = build_targets(sheets, starting_number)
    conflicts = find_conflicts(targets, sheets, all_sheets)
    if conflicts:
        forms.alert(
            "Os números abaixo já existem em pranchas que não foram selecionadas:\n\n"
            + "\n".join(sheet_label(s) for s in conflicts)
            + "\n\nEscolha outro número inicial ou inclua essas pranchas na seleção."
        )
        continue

    if forms.alert(
        "Confirma a renumeração?\n\n" + preview_text(sheets, targets),
        yes=True,
        no=True,
    ):
        break

try:
    renumber(sheets, targets)
    helpers.log("{} pranchas renumeradas.".format(len(sheets)))
except Exception:
    helpers.print_error("Falha ao renumerar pranchas")
