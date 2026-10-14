# -*- coding: utf-8 -*-
import os
from symtable import Class
import traceback
from datetime import datetime
from collections import OrderedDict

from Autodesk.Revit.DB import (
    Element,
    ElementClassFilter,
    FilteredElementCollector,
    ModelPathUtils,
    OpenOptions,
    RevitLinkInstance,
    RevitLinkType,
)



def log(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print("[{}] {}".format(timestamp, message))

def print_error(context):
    log("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")
    log("ERRO: {}".format(context))
    traceback.print_exc()
    log("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")

class VisitQueue(object):
    def __init__(self):
        self._visit_queue = OrderedDict()
        self._visited = set()

    def add(self, entries):
        added = 0
        skipped = []
        for path, value in entries.items():
            if path in self._visited or path in self._visit_queue:
                skipped.append(path)
            else:
                self._visit_queue[path] = value
                added += 1
        return added, skipped

    def pop(self):
        if self._visit_queue:
            next_entry = self._visit_queue.popitem(last=False)
            self._visited.add(next_entry[0])
            return next_entry

    def __len__(self):
        return len(self._visit_queue)


def make_entry(model_path, name):
    path = ModelPathUtils.ConvertModelPathToUserVisiblePath(model_path).upper()
    return path, {"model_path": model_path, "name": name}


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
        path, value = make_entry(model_path, name)
        entries[path] = value
    return entries


def entries_from_files(file_paths):
    entries = OrderedDict()
    for file_path in file_paths:
        model_path = ModelPathUtils.ConvertUserVisiblePathToModelPath(file_path)
        path, value = make_entry(model_path, os.path.basename(file_path))
        entries[path] = value
    return entries

def visit_file():

def get_queue_from_links(link_list):
    log("[{}] Encontrados {} vinculos no total".format(doc.Title, len(links)))
    _visit_queue = {}
    for link in link_list:
        if link.IsNestedLink:
            log("  [{}] Ignorando '{}' (link aninhado)".format(doc.Title, name))
            continue
        if not has_instance:
            log("  [{}] Ignorando '{}' (sem instancia)".format(doc.Title, name))
            continue
        name = Element.Name.GetValue(link)
        link_file_ref = link.GetExternalFileReference()
        model_path = link_file_ref.GetAbsolutePath()
        path = ModelPathUtils.ConvertModelPathToUserVisiblePath(model_path).upper()
        if path in _visit_queue.keys() or path in visited:
            log(
                "  [{}] Ignorando '{}' (ja na fila ou processado)".format(
                    doc.Title, name
                )
            )
            continue

        _visit_queue[path] = {}
        _visit_queue[path]["link"] = link
        _visit_queue[path]["link_name"] = name
        _visit_queue[path]["model_path"] = model_path

    return _visit_queue

def read__files(file_source):



def read_links(doc, visited):
    if visited is None:
        visited = []
    links = FilteredElementCollector(doc).OfClass(RevitLinkType).ToElements()
    instance_filter = ElementClassFilter(RevitLinkInstance)
    valid_count = 0

    for link in links:
        name = Element.Name.GetValue(link)
        has_instance = len(link.GetDependentElements(instance_filter)) > 0
        path, model_path = get_paths(link)
        valid_count += 1
        _visit_queue[path] = {}
        _visit_queue[path]["link"] = link
        _visit_queue[path]["link_name"] = name
        _visit_queue[path]["model_path"] = model_path
    log("[{}] {} vinculos validos adicionados a fila".format(doc.Title, valid_count))
    return _visit_queue


def unload_links(doc, unloaded, visited=None):
    _visit_queue = {}
    _visit_queue = read_links(doc, _visit_queue, visited)
    for path, value in _visit_queue.items():
        link = value["link"]
        if link.IsLoaded:
            link.Unload(None)
            unloaded.append(link)
            log("[{}] '{}' descarregado".format(doc.Title, value["link_name"]))
    return unloaded, _visit_queue


def visit_link(app, value, _visit_queue, visited, main_function, recursive=True):

    open_options = OpenOptions()
    model_path = value["model_path"]
    linked_document = None
    try:
        linked_document = app.OpenDocumentFile(model_path, open_options)
        log("Abrindo: {}".format(linked_document.Title))

        if recursive:
            _visit_queue = read_links(linked_document, _visit_queue, visited)

        main_function(linked_document, value)

    except Exception:
        print_error("Falha ao processar link: {}".format(value.get("link_name")))

    finally:
        if linked_document is not None:
            log("Fechando: {}".format(linked_document.Title))
            linked_document.Close()

    return _visit_queue


def proccess_queue(app, _visit_queue, visited, main_function, recursive=True):
    while _visit_queue:
        path, value = _visit_queue.popitem()
        _visit_queue = visit_link(
            app, value, _visit_queue, visited, main_function, recursive
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


def reload_links(links):
    """Recarrega uma lista de RevitLinkType (ex.: a lista 'unloaded')."""
    for link in links:
        name = Element.Name.GetValue(link)
        try:
            link.Reload()
            log("'{}' recarregado".format(name))
        except Exception:
            print_error("Falha ao recarregar '{}'".format(name))

def pick_elements(element_class, prompt):
    elements = FilteredElementCollector(doc).OfClass(element_class).ToElements()
    name_to_elem = {Element.Name.GetValue(e): e for e in elements}
    selected_elements = forms.SelectFromList.show(
        list(name_to_elem.keys()),
        title=prompt,
        multiselect=True,
    )
    return [name_to_elem[name] for name in selected_elements]