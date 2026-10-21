# -*- coding: utf-8 -*-
import os
import traceback
from datetime import datetime
from collections import OrderedDict
from pyrevit import forms

from Autodesk.Revit.DB import (
    Element,
    ElementClassFilter,
    FilteredElementCollector,
    ModelPathUtils,
    OpenOptions,
    RevitLinkInstance,
    RevitLinkType,
)


#### LOGGING ####

def log(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print("[{}] {}".format(timestamp, message))

def print_error(context):
    log("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")
    log("ERRO: {}".format(context))
    traceback.print_exc()
    log("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")

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


#### FILE QUEUEING ####

class VisitQueue(object):
    def __init__(self):
        self._visit_queue = OrderedDict()
        self._visited = set()

    def add(self, entries):
        added = 0
        skipped = []
        for path, entry in entries.items():
            if path in self._visited or path in self._visit_queue:
                skipped.append(path)
            else:
                self._visit_queue[path] = entry
                added += 1
        return added, skipped

    def pop(self):
        if self._visit_queue:
            next_entry = self._visit_queue.popitem(last=False)
            self._visited.add(next_entry[0])
            return next_entry

    def mark_visited(self, path):
        self._visited.add(path)
        self._visit_queue.pop(path, None)

    def __len__(self):
        return len(self._visit_queue)

def path_key(model_path):
    return ModelPathUtils.ConvertModelPathToUserVisiblePath(model_path).upper()

def doc_path_key(doc):
    """Chave de um documento aberto, no mesmo formato das chaves da fila."""
    if doc.IsWorkshared:
        return path_key(doc.GetWorksharingCentralModelPath())
    if doc.PathName:
        return path_key(ModelPathUtils.ConvertUserVisiblePathToModelPath(doc.PathName))
    return None

def make_entry(model_path, name):
    return path_key(model_path), {"model_path": model_path, "name": name}

def collect_valid_links(doc):
    links = FilteredElementCollector(doc).OfClass(RevitLinkType).ToElements()
    valid_links = []
    instance_filter = ElementClassFilter(RevitLinkInstance)

    for link in links:
        name = Element.Name.GetValue(link)

        if link.IsNestedLink:
            log("  [{}] Ignorando '{}' (link aninhado)".format(doc.Title, name))
            continue
        if len(link.GetDependentElements(instance_filter)) == 0:
            log("  [{}] Ignorando '{}' (sem instancia)".format(doc.Title, name))
            continue

        valid_links.append(link)

    return valid_links

def entries_from_links(valid_links):
    entries = OrderedDict()
    for link in valid_links:
        name = Element.Name.GetValue(link)
        model_path = link.GetExternalFileReference().GetAbsolutePath()
        path, entry = make_entry(model_path, name)
        entries[path] = entry
    return entries

def entries_from_files(file_paths):
    entries = OrderedDict()
    for file_path in file_paths:
        model_path = ModelPathUtils.ConvertUserVisiblePathToModelPath(file_path)
        path, entry = make_entry(model_path, os.path.basename(file_path))
        entries[path] = entry
    return entries

def visit_file(app, entry, main_function, discover=None):
    open_options = OpenOptions()
    model_path = entry["model_path"]
    opened_file = None
    new_entries = OrderedDict()
    try:
        opened_file = app.OpenDocumentFile(model_path, open_options)
        log("Abrindo: {}".format(opened_file.Title))

        if discover:
            new_entries.update(discover(opened_file))

        main_function(opened_file)

    except Exception:
        print_error("Falha ao processar link: {}".format(entry.get("name")))

    finally:
        if opened_file is not None:
            log("Fechando: {}".format(opened_file.Title))
            opened_file.Close()

    return new_entries

def unload_links(links):
    """Descarrega uma lista de RevitLinkType e devolve os que foram descarregados."""
    unloaded = []
    for link in links:
        name = Element.Name.GetValue(link)
        if link.IsLoaded:
            link.Unload(None)
            unloaded.append(link)
            log("'{}' descarregado".format(name))
    return unloaded

def process_queue(app, queue, main_function, discover=None):
    while queue:
        path, next_entry = queue.pop()
        new_entries = visit_file(app, next_entry, main_function, discover)
        queue.add(new_entries)

def reload_links(links):
    """Recarrega uma lista de RevitLinkType (ex.: a lista 'unloaded')."""
    for link in links:
        name = Element.Name.GetValue(link)
        try:
            link.Reload()
            log("'{}' recarregado".format(name))
        except Exception:
            print_error("Falha ao recarregar '{}'".format(name))


### USER PROMPTING ###

def pick_elements(doc, element_class, prompt):
    elements = FilteredElementCollector(doc).OfClass(element_class).ToElements()
    name_to_elem = {Element.Name.GetValue(e): e for e in elements}
    selected_elements = forms.SelectFromList.show(
        list(name_to_elem.keys()),
        title=prompt,
        multiselect=True,
    )
    if not selected_elements:
        return []
    return [name_to_elem[name] for name in selected_elements]
