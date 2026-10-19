from Autodesk.Revit.DB import (
    DWGExportOptions,
    Element,
    FilteredElementCollector,
    Revision,
    RevitLinkInstance,
    RevitLinkType,
    ViewSheet,
    ViewType,
)
from pyrevit import forms, script
import helpers

uidoc = __revit__.ActiveUIDocument
doc = uidoc.Document
app = __revit__.Application
current_view = uidoc.ActiveView

def main_function(opened_file, data=None):
    sheets = helpers.pick_elements(opened_file, ViewSheet, "Selecione as pranchas a serem exportadas")
    new_revision = normalize_revision(sheets, revision_info)
    new_revision_to_sheet(new_revision, sheets)

def export_dwg(opened_file, target_folder, sheet_ids, dwg_export_options):
    opened_file.Export(target_folder, '', sheet_ids, dwg_export_options)


def new_revision_to_sheet(new_revision, sheets):
    for sheet in sheets:
        sheet.SetAdditionalRevisionIds(new_revision)

def normalize_revision(sheets, revision_info):
    for sheet in sheets:
        sheet_revision = Element.GetElement(sheet.GetCurrentRevision())
        if sheet_revision.Description != revision_info["description"]:
            new_revision = Revision.Create
            new_revision.Description = revision_info["description"]
            new_revision.Issued = revision_info["issued"]  
            new_revision.IssuedBy = revision_info["issued_by"]
            new_revision.IssuedTo = revision_info["issued_to"] 
            new_revision.RevisionDate = revision_info["date"]
        else:
            new_revision = sheet_revision
    return new_revision

# Pick folder and files to export

target_folder = forms.pick_folder(title="Selecione a pasta de destino para exportação")
if not target_folder:
    forms.alert("Nenhuma pasta de destino selecionada.", exitscript=True)

# Pick links where there are sheets to export
selected_links = helpers.pick_elements(
    doc, RevitLinkType, "Selecione os links que contem as pranchas a serem exportadas"
)

if current_view.ViewType != ViewType.ViewSheet:
    forms.alert(
        "Por favor, abra uma prancha antes de executar o script.",
        exitscript=True,
    )


# Get the current revision of the sheet to be used for export and prompts user for confirmation
revision = Element.GetElement(current_view.GetCurrentRevision())
revision_info = {
    "description": revision.Description,
    "issued": revision.Issued,
    "issued_by": revision.IssuedBy,
    "issued_to": revision.IssuedTo,
    "date": revision.RevisionDate
}

if not forms.alert(
    "A revisão atual da prancha será usada para exportação: {}. Prosseguir?".format(
        revision_info["description"]
    ),
    yes=True,
    no=True
):
    script.exit()

# Read links
dwg_export_options = DWGExportOptions()
dwg_export_options.GetPredefinedOptions(doc, "DWG")

queue = helpers.VisitQueue()

unloaded_links = helpers.unload_links(selected_links)
entries = helpers.entries_from_links(unloaded_links)
queue.add(entries)





