# -*- coding: utf-8 -*-
from Autodesk.Revit.DB import (
    BuiltInCategory,
    BuiltInParameter,
    Element,
    FilteredElementCollector,
    Transaction,
)
from pyrevit import forms, script

import helpers
from helpers import log, print_error

CATEGORIES = [
    (BuiltInCategory.OST_Floors, "Pisos"),
    (BuiltInCategory.OST_Walls, "Paredes"),
    (BuiltInCategory.OST_Doors, "Portas"),
    (BuiltInCategory.OST_Windows, "Janelas"),
]


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


def discover_links(opened_doc):
    valid = helpers.collect_valid_links(opened_doc)
    log("[{}] {} vinculos validos encontrados".format(opened_doc.Title, len(valid)))
    return helpers.entries_from_links(valid)


def process_document(target_doc):
    copy_type_mark_to_keynote(target_doc, update_log, skipped_log)


uidoc = __revit__.ActiveUIDocument
doc = uidoc.Document
app = __revit__.Application

if not forms.alert(
    "A marca de tipo sera copiada para a nota-chave dos tipos de pisos, paredes, "
    "portas e janelas neste arquivo e em todos os vinculos (que serao abertos, "
    "salvos e fechados).\n\nProsseguir?",
    yes=True,
    no=True,
):
    script.exit()

log("Iniciando")

update_log = {}
skipped_log = {}
unloaded = []
try:
    queue = helpers.VisitQueue()
    queue.mark_visited(helpers.doc_path_key(doc))

    valid_links = helpers.collect_valid_links(doc)
    unloaded = helpers.unload_links(valid_links)
    queue.add(helpers.entries_from_links(valid_links))

    process_document(doc)

    helpers.process_queue(app, queue, process_document, discover=discover_links)

    helpers.print_summary(
        update_log,
        skipped_log,
        updated_msg="Nota-chave do tipo {} atualizada nos arquivos: {}",
        empty_msg="Nenhum tipo foi atualizado.",
        skipped_msg="Tipos bloqueados (nao modificados): {}",
    )
except Exception:
    print_error("Falha geral no script")
finally:
    helpers.reload_links(unloaded)
