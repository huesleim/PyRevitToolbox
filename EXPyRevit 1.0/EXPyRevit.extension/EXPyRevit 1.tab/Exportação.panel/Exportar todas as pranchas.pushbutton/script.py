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


def pick_elements(element_class, prompt):
    elements = FilteredElementCollector(doc).OfClass(element_class).ToElements()
    name_to_elem = {Element.Name.GetValue(e): e for e in elements}
    selected_elements = forms.SelectFromList.show(
        list(name_to_elem.keys()),
        title=prompt,
        multiselect=True,
    )
    return [name_to_elem[name] for name in selected_elements]


uidoc = __revit__.ActiveUIDocument
doc = uidoc.Document
app = __revit__.Application
current_view = uidoc.ActiveView

# Pick .txt file for dwg exporting config
dwg_export = forms.pick_file(
    file_ext="txt", title="Selecione o arquivo de configuração de exportação DWG"
)
if not dwg_export:
    forms.alert("Nenhum arquivo de configuração de exportação DWG selecionado.", exitscript=True)

target_folder = forms.pick_folder(title="Selecione a pasta de destino para exportação")
if not target_folder:
    forms.alert("Nenhuma pasta de destino selecionada.", exitscript=True)

# Pick links where there are sheets to export
while True:
    selected_links = pick_elements(RevitLinkType, "Selecione os vínculos onde há arquivos a serem exportados")
    if not selected_links:
        forms.alert("Nenhum vínculo selecionado. O script será encerrado.", exitscript=True)
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
for link in selected_links:
    selected_sheets = pick_elements(ViewSheet, "Selecione as pranchas para exportação".format(link.Name))
    link_doc = link.GetLinkDocument()
    existing_revisions = FilteredElementCollector(doc).OfClass(RevitLinkInstance).ToElements()
    if existing_revisions[0].Description != revision_info["description"]:
        new_revision = Revision.Create(link_doc)
        new_revision.Description = revision_info["description"]
        new_revision.Issued = revision_info["issued"]
        new_revision.IssuedBy = revision_info["issued_by"]
        new_revision.IssuedTo = revision_info["issued_to"]
        new_revision.RevisionDate = revision_info["date"]
    else:
        new_revision = existing_revisions[0]

    for sheet in selected_sheets:
        sheet.SetAdditionalRevisionIds(new_revision.Id)

        doc.Export(
            target_folder,
            sheet.SheetNumber + "_" + sheet.Name,
            sheet,
            DWGExportOptions(dwg_export),
        )


# Propriedades de PDFExportOptions anotadas para referência (estavam soltas no
# fim do arquivo e quebravam a execução):
# AlwaysUseRaster, ColorDepth, Combine, ExportQuality, FileName,
# HideCropBoundaries, HideReferencePlane, HideScopeBoxes,
# HideUnreferencedViewTags, IsValidObject, MaskCoincidentLines,
# OriginOffsetX, OriginOffsetY, PaperFormat, PaperOrientation,
# PaperPlacement, RasterQuality, ReplaceHalftoneWithThinLines, StopOnError,
# ViewLinksInBlue, ZoomPercentage, ZoomType

# Documento elaborado com auxílio do programa de incentivo à IA EXP Brasil