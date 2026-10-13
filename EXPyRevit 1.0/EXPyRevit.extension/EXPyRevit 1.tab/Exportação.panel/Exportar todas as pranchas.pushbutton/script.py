import traceback
from datetime import datetime

from Autodesk.Revit.DB import (
    BuiltInParameter,
    Element,
    ElementClassFilter,
    ElementId,
    ExternalResourceReference,
    ExternalResourceTypes,
    FilteredElementCollector,
    KeynoteTable,
    ModelPathUtils,
    OpenOptions,
    PathType,
    Revision,
    RevitLinkInstance,
    RevitLinkType,
    ScheduleFilter,
    ScheduleFilterType,
    Transaction,
    ViewSchedule,
    ViewType
)
from Autodesk.Revit.Exceptions import OperationCanceledException
from pyrevit import forms, script


def log(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print("[{}] {}".format(timestamp, message))


def print_error(context):
    log("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")
    log("ERRO: {}".format(context))
    traceback.print_exc()
    log("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")


def get_paths(link):
    link_file_ref = link.GetExternalFileReference()
    model_path = link_file_ref.GetAbsolutePath()
    path_string = ModelPathUtils.ConvertModelPathToUserVisiblePath(model_path).upper()
    return path_string, model_path


def read_links(doc, visit_queue, visited):
    if visited is None:
        visited = []
    links = FilteredElementCollector(doc).OfClass(RevitLinkType).ToElements()
    log("[{}] Encontrados {} vinculos no total".format(doc.Title, len(links)))
    instance_filter = ElementClassFilter(RevitLinkInstance)
    valid_count = 0
    for link in links:
        name = Element.Name.GetValue(link)
        has_instance = len(link.GetDependentElements(instance_filter)) > 0
        if link.IsNestedLink:
            log("  [{}] Ignorando '{}' (link aninhado)".format(doc.Title, name))
            continue
        if not has_instance:
            log("  [{}] Ignorando '{}' (sem instancia)".format(doc.Title, name))
            continue
        path, model_path = get_paths(link)
        if path in visit_queue.keys() or path in visited:
            log(
                "  [{}] Ignorando '{}' (ja na fila ou processado)".format(
                    doc.Title, name
                )
            )
            continue
        valid_count += 1
        visit_queue[path] = {}
        visit_queue[path]["link"] = link
        visit_queue[path]["link_name"] = name
        visit_queue[path]["model_path"] = model_path
    log("[{}] {} vinculos validos adicionados a fila".format(doc.Title, valid_count))
    return visit_queue


def unload_links(doc, unloaded, visited=None):
    visit_queue = {}
    visit_queue = read_links(doc, visit_queue, visited)
    for path, value in visit_queue.items():
        link = value["link"]
        if link.IsLoaded:
            link.Unload(None)
            unloaded.append(link)
            log("[{}] '{}' descarregado".format(doc.Title, value["link_name"]))
    return unloaded, visit_queue


def reload_keynote_table(doc, keynote_file_ref):
    try:
        t = Transaction(doc, "Recarregando tabela de nota-chave no arquivo atual")
        t.Start()
        keynote_table = KeynoteTable.GetKeynoteTable(doc)
        keynote_table.LoadFrom(keynote_file_ref, None)
        t.Commit()
        log("[{}] Tabela de nota-chave recarregada".format(doc.Title))
        return keynote_table

    except Exception:
        print_error("Falha ao recarregar tabela de nota-chave em {}".format(doc.Title))
        return None


def build_keynote_lookup(keynote_table):
    lookup = {}
    if keynote_table is None:
        return lookup
    for entry in keynote_table.GetKeyBasedTreeEntries():
        lookup[entry.Key] = entry.KeynoteText
    return lookup


def get_keynote_value(elem, doc):
    type_id = elem.GetTypeId()
    if type_id == ElementId.InvalidElementId:
        return None, None

    type_elem = doc.GetElement(type_id)
    type_param = type_elem.get_Parameter(BuiltInParameter.KEYNOTE_PARAM)
    value = type_param.AsString() if type_param else None
    return value, type_param


def update_descriptions(doc, keynote_lookup, update_log, skipped_log):
    existing = next(
        (
            s
            for s in FilteredElementCollector(doc).OfClass(ViewSchedule).ToElements()
            if s.Name == "Nota-chave e descricao"
        ),
        None,
    )

    t = Transaction(
        doc, "Criando tabela e atualizando descricoes a partir da nota-chave"
    )
    t.Start()

    try:
        if existing:
            schedule = existing
        else:
            schedule = ViewSchedule.CreateSchedule(doc, ElementId.InvalidElementId)
            schedule.Name = "Nota-chave e descricao"
            definition = schedule.Definition
            schedulable_fields = definition.GetSchedulableFields()
            keynote_field = next(
                f for f in schedulable_fields if f.GetName(doc) == "Nota-chave"
            )
            field = definition.AddField(keynote_field)
            keynote_filter = ScheduleFilter(
                field.FieldId, ScheduleFilterType.NotEqual, ""
            )
            definition.AddFilter(keynote_filter)

        elements = list(FilteredElementCollector(doc, schedule.Id).ToElements())
        local_updates = {}
        local_skips = {}

        for elem in elements:
            keynote_value, _ = get_keynote_value(elem, doc)
            if not keynote_value:
                continue

            description_value = keynote_lookup.get(keynote_value)

            type_id = elem.GetTypeId()
            if type_id == ElementId.InvalidElementId:
                local_skips.setdefault(keynote_value, []).append(doc.Title)
                continue

            type_elem = doc.GetElement(type_id)
            description_param = type_elem.get_Parameter(
                BuiltInParameter.ALL_MODEL_DESCRIPTION
            )

            if (
                description_value
                and description_param
                and not description_param.IsReadOnly
            ):
                description_param.Set(description_value)
                local_updates.setdefault(keynote_value, []).append(doc.Title)
            else:
                local_skips.setdefault(keynote_value, []).append(doc.Title)

        t.Commit()
        log(
            "[{}] Tabela '{}' processada, {} elementos atualizados".format(
                doc.Title, schedule.Name, len(local_updates)
            )
        )

        for key, files in local_updates.items():
            update_log.setdefault(key, []).extend(files)
        for key, files in local_skips.items():
            skipped_log.setdefault(key, []).extend(files)

    except OperationCanceledException:
        log("[{}] Operacao cancelada, nenhuma alteracao foi salva".format(doc.Title))
        t.Rollback()

    except Exception:
        print_error(
            "Falha ao criar tabela/atualizar descricoes em {}".format(doc.Title)
        )
        t.Rollback()

def visit_link(
    app, value, visit_queue, visited, keynote_file_ref, update_log, skipped_log
):
    open_options = OpenOptions()
    model_path = value["model_path"]
    try:
        linked_document = app.OpenDocumentFile(model_path, open_options)
        log("Abrindo: {}".format(linked_document.Title))

        visit_queue = read_links(linked_document, visit_queue, visited)

        keynote_table = reload_keynote_table(linked_document, keynote_file_ref)
        keynote_lookup = build_keynote_lookup(keynote_table)
        update_descriptions(linked_document, keynote_lookup, update_log, skipped_log)

        log("Fechando: {}".format(linked_document.Title))
        linked_document.Close()

    except Exception:
        print_error("Falha ao processar link: {}".format(model_path))

    return visit_queue


def proccess_queue(
    app, visit_queue, visited, keynote_file_ref, update_log, skipped_log
):
    while visit_queue:
        path, value = visit_queue.popitem()
        visit_queue = visit_link(
            app, value, visit_queue, visited, keynote_file_ref, update_log, skipped_log
        )
        visited.append(path)


def print_summary(update_log, skipped_log):
    log("\n===== RESUMO =====")
    if update_log:
        for key, files in update_log.items():
            unique_files = sorted(set(files))
            log(
                "Descricao do elemento {} atualizada nos arquivos: {}".format(
                    key, ", ".join(unique_files)
                )
            )
    else:
        log("Nenhum elemento foi atualizado.")

    if skipped_log:
        skipped_keys = sorted(skipped_log.keys())
        log("Elementos nao modificados: {}".format(", ".join(skipped_keys)))
    log("==================")

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

if current_view.ViewType != ViewType.ViewSheet:
    forms.alert(
        "Por favor, abra uma prancha antes de executar o script.",
        exitscript=True,
    )


# Get the current revision of the sheet to be used for export and prompts user for confirmation
revision = Element.GetElement(current_view.GetCurrentRevision)
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


AlwaysUseRaster

ColorDepth

Combine

ExportQuality

FileName

HideCropBoundaries

HideReferencePlane

HideScopeBoxes

HideUnreferencedViewTags

IsValidObject

MaskCoincidentLines

OriginOffsetX

OriginOffsetY

PaperFormat

PaperOrientation

PaperPlacement

RasterQuality

ReplaceHalftoneWith ThinLines

StopOnError

ViewLinksInBlue

ZoomPercentage

ZoomType