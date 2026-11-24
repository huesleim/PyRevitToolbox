import traceback
from datetime import datetime

from Autodesk.Revit.DB import (
    BuiltInCategory,
    BuiltInParameter,
    Element,
    ElementClassFilter,
    FilteredElementCollector,
    ModelPathUtils,
    OpenOptions,
    RevitLinkInstance,
    RevitLinkType,
    Transaction,
)

CATEGORIES = [
    (BuiltInCategory.OST_Floors, "Pisos"),
    (BuiltInCategory.OST_Walls, "Paredes"),
    (BuiltInCategory.OST_Doors, "Portas"),
    (BuiltInCategory.OST_Windows, "Janelas"),
    (BuiltInCategory.OST_PlumbingFixtures, "Peças Hidrossanitárias")
]


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


def type_label(elem_type):
    return "{}: {}".format(elem_type.FamilyName, Element.Name.GetValue(elem_type))


def get_type_mark(elem_type):
    param = elem_type.get_Parameter(BuiltInParameter.ALL_MODEL_TYPE_MARK)
    if param is None:
        param = elem_type.get_Parameter(BuiltInParameter.WINDOW_TYPE_ID)
    return param.AsString() if param else None


def copy_type_mark_to_keynote(doc, update_log, skipped_log):
    t = Transaction(doc, "Copiando marca de tipo para nota-chave")
    t.Start()
    try:
        local_updates = {}
        local_skips = {}

        for category, label in CATEGORIES:
            types = (
                FilteredElementCollector(doc)
                .OfCategory(category)
                .WhereElementIsElementType()
                .ToElements()
            )
            changed = same = empty = blocked = 0

            for elem_type in types:
                name = type_label(elem_type)
                type_mark = get_type_mark(elem_type)
                key_param = elem_type.get_Parameter(BuiltInParameter.KEYNOTE_PARAM)

                if not type_mark:
                    empty += 1
                    continue
                if key_param is None or key_param.IsReadOnly:
                    blocked += 1
                    local_skips.setdefault(name, []).append(doc.Title)
                    continue
                if key_param.AsString() == type_mark:
                    same += 1
                    continue

                key_param.Set(type_mark)
                changed += 1
                local_updates.setdefault(name, []).append(doc.Title)
                log("  [{}] {} -> '{}'".format(doc.Title, name, type_mark))

            log(
                "[{}] {}: {} tipos | {} alterados, {} ja iguais, "
                "{} sem marca de tipo, {} bloqueados".format(
                    doc.Title, label, len(types), changed, same, empty, blocked
                )
            )

        t.Commit()

        for key, files in local_updates.items():
            update_log.setdefault(key, []).extend(files)
        for key, files in local_skips.items():
            skipped_log.setdefault(key, []).extend(files)

    except Exception:
        t.RollBack()
        print_error("Falha ao copiar marca de tipo para nota-chave em {}".format(doc.Title))


def visit_link(app, value, visit_queue, visited, update_log, skipped_log):
    open_options = OpenOptions()
    model_path = value["model_path"]
    try:
        linked_document = app.OpenDocumentFile(model_path, open_options)
        log("Abrindo: {}".format(linked_document.Title))

        visit_queue = read_links(linked_document, visit_queue, visited)

        copy_type_mark_to_keynote(linked_document, update_log, skipped_log)

        log("Fechando: {}".format(linked_document.Title))
        linked_document.Close()

    except Exception:
        print_error("Falha ao processar link: {}".format(model_path))

    return visit_queue


def proccess_queue(app, visit_queue, visited, update_log, skipped_log):
    while visit_queue:
        path, value = visit_queue.popitem()
        visit_queue = visit_link(
            app, value, visit_queue, visited, update_log, skipped_log
        )
        visited.append(path)


def print_summary(update_log, skipped_log):
    log("\n===== RESUMO =====")
    if update_log:
        for key, files in update_log.items():
            unique_files = sorted(set(files))
            log(
                "Nota-chave do tipo {} atualizada nos arquivos: {}".format(
                    key, ", ".join(unique_files)
                )
            )
    else:
        log("Nenhum tipo foi atualizado.")

    if skipped_log:
        skipped_keys = sorted(skipped_log.keys())
        log("Tipos bloqueados (nao modificados): {}".format(", ".join(skipped_keys)))
    log("==================")


uidoc = __revit__.ActiveUIDocument
doc = uidoc.Document
app = __revit__.Application

log("Iniciando")

visit_queue = {}
unloaded = []
visited = []
update_log = {}
skipped_log = {}
try:
    unloaded, visit_queue = unload_links(doc, unloaded, visited)

    copy_type_mark_to_keynote(doc, update_log, skipped_log)

    proccess_queue(app, visit_queue, visited, update_log, skipped_log)

    for link in unloaded:
        link.Reload()

    print_summary(update_log, skipped_log)
except Exception:
    print_error("Falha geral no script")