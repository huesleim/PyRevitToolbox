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
    RevitLinkInstance,
    RevitLinkType,
    ScheduleFilter,
    ScheduleFilterType,
    Transaction,
    ViewSchedule,
)
from Autodesk.Revit.Exceptions import OperationCanceledException
from pyrevit import forms


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


def visit_link(
    app, value, visit_queue, visited, main_function
):
    open_options = OpenOptions()
    model_path = value["model_path"]
    try:
        linked_document = app.OpenDocumentFile(model_path, open_options)
        log("Abrindo: {}".format(linked_document.Title))

        visit_queue = read_links(linked_document, visit_queue, visited)

        main_function(linked_document)

        log("Fechando: {}".format(linked_document.Title))

    except Exception:
        print_error("Falha ao processar link: {}".format(model_path))

    finally:
        linked_document.Close()

    return visit_queue


def proccess_queue(
    app, visit_queue, visited, main_function
):
    while visit_queue:
        path, value = visit_queue.popitem()
        visit_queue = visit_link(
            app, value, visit_queue, visited, main_function=
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

def reload_links(visited):
    for link in visited:
        link.Reload()