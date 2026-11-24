# -*- coding: utf-8 -*-
from Autodesk.Revit.DB import (
    BuiltInParameter,
    ElementId,
    ExternalResourceReference,
    ExternalResourceTypes,
    FilteredElementCollector,
    KeynoteTable,
    ModelPathUtils,
    PathType,
    ScheduleFilter,
    ScheduleFilterType,
    Transaction,
    ViewSchedule,
)
from Autodesk.Revit.Exceptions import OperationCanceledException
from pyrevit import forms, script

import helpers
from helpers import log, print_error


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
        t.RollBack()

    except Exception:
        print_error(
            "Falha ao criar tabela/atualizar descricoes em {}".format(doc.Title)
        )
        t.RollBack()


def discover_links(opened_doc):
    valid = helpers.collect_valid_links(opened_doc)
    log("[{}] {} vinculos validos encontrados".format(opened_doc.Title, len(valid)))
    return helpers.entries_from_links(valid)


def process_document(target_doc):
    keynote_table = reload_keynote_table(target_doc, keynote_file_ref)
    keynote_lookup = build_keynote_lookup(keynote_table)
    update_descriptions(target_doc, keynote_lookup, update_log, skipped_log)


uidoc = __revit__.ActiveUIDocument
doc = uidoc.Document
app = __revit__.Application

keynote_file = forms.pick_file(
    file_ext="txt", title="Selecione o arquivo da tabela de nota-chave"
)
if not keynote_file:
    forms.alert("Nenhum arquivo de tabela de nota-chave selecionado.", exitscript=True)

if not forms.alert(
    "A tabela de nota-chave sera recarregada e as descricoes atualizadas neste "
    "arquivo e em todos os vinculos (que serao abertos, salvos e fechados).\n\n"
    "Prosseguir?",
    yes=True,
    no=True,
):
    script.exit()

model_path = ModelPathUtils.ConvertUserVisiblePathToModelPath(keynote_file)
keynote_file_ref = ExternalResourceReference.CreateLocalResource(
    doc,
    ExternalResourceTypes.BuiltInExternalResourceTypes.KeynoteTable,
    model_path,
    PathType.Absolute,
)

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

    helpers.print_summary(update_log, skipped_log)
except Exception:
    print_error("Falha geral no script")
finally:
    helpers.reload_links(unloaded)
