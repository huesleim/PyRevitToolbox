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

# Pick folder and files to export
target_files = forms.pick_files(
    file_ext="rvt",
    title="Selecione os arquivos de destino para exportação",
)

target_folder = forms.pick_folder(title="Selecione a pasta de destino para exportação")
if not target_folder:
    forms.alert("Nenhuma pasta de destino selecionada.", exitscript=True)

# Pick links where there are sheets to export
while True:
    selected_links = helpers.pick_elements(RevitLinkType, "Selecione os vínculos onde há arquivos a serem exportados")
    if not selected_links:
        forms.alert("Nenhum vínculo selecionado.", exitscript=True)
        continue
    break

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
dwg_export = DWGExportOptions()
dwg_export.GetPredefinedOptions(doc, "DWG")

visit_queue = helpers.read_links(doc, None)


helpers.unload_links(doc,visit_queue,selected_links)

for file in target_files:
    


    selected_sheets = helpers.pick_elements(ViewSheet, "Selecione as pranchas para exportação".format(link.Name))
    link_doc = link.GetLinkDocument()
    existing_revisions = list(GetAllRevisionIds(link_doc))
    last_revision = doc.GetElement(existing_revisions[-1]) if existing_revisions else None
    if last_revision.Description != revision_info["description"]:
        new_revision = Revision.Create(link_doc)
        new_revision.Description = revision_info["description"]
        new_revision.Issued = revision_info["issued"]
        new_revision.IssuedBy = revision_info["issued_by"]
        new_revision.IssuedTo = revision_info["issued_to"]
        new_revision.RevisionDate = revision_info["date"]
    else:
        new_revision = last_revision

    for sheet in selected_sheets:
        sheet.SetAdditionalRevisionIds(new_revision.Id)

        doc.Export(
            target_folder,
            sheet.SheetNumber + "_" + sheet.Name,
            sheet,
            DWGExportOptions(dwg_export),
        )


