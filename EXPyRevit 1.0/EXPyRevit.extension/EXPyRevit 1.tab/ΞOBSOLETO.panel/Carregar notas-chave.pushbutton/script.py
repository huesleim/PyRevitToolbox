import traceback

from Autodesk.Revit.DB import (
    Element,
    ElementClassFilter,
    ExternalResourceReference,
    ExternalResourceTypes,
    FilteredElementCollector,
    KeynoteTable,
    ModelPathUtils,
    OpenOptions,
    PathType,
    RevitLinkInstance,
    RevitLinkType,
    Transaction,
)
from pyrevit import forms


def get_paths(link):
    link_file_ref = link.GetExternalFileReference()
    model_path = link_file_ref.GetAbsolutePath()
    path_string = ModelPathUtils.ConvertModelPathToUserVisiblePath(model_path).upper()
    return path_string, model_path


def read_links(doc, visit_queue, visited):
    if visited is None:
        visited = []
    links = FilteredElementCollector(doc).OfClass(RevitLinkType).ToElements()
    print("[{}] Encontrados {} vinculos no total".format(doc.Title, len(links)))
    instance_filter = ElementClassFilter(RevitLinkInstance)
    valid_count = 0
    for link in links:
        name = Element.Name.GetValue(link)
        has_instance = len(link.GetDependentElements(instance_filter)) > 0
        if link.IsNestedLink:
            print("  Ignorando '{}' (link aninhado)".format(name))
            continue
        if not has_instance:
            print("  Ignorando '{}' (sem instancia)".format(name))
            continue
        path, model_path = get_paths(link)
        if path in visit_queue.keys() or path in visited:
            print("  Ignorando '{}' (ja na fila ou processado)".format(name))
            continue
        valid_count += 1
        visit_queue[path] = {}
        visit_queue[path]["link"] = link
        visit_queue[path]["link_name"] = name
        visit_queue[path]["model_path"] = model_path
    print("[{}] {} vinculos validos adicionados a fila".format(doc.Title, valid_count))
    return visit_queue


def unload_links(doc, unloaded, visited=None):
    visit_queue = {}
    visit_queue = read_links(doc, visit_queue, visited)
    for path, value in visit_queue.items():
        link = value["link"]
        if link.IsLoaded:
            link.Unload(None)
            unloaded.append(link)
            print("[{}] '{}' descarregado".format(doc.Title, value["link_name"]))
    return unloaded, visit_queue


def reload_keynote_table(doc, keynote_file_ref):
    try:
        t = Transaction(doc, "Recarregando tabela de nota-chave no arquivo atual")
        t.Start()
        keynote_table = KeynoteTable.GetKeynoteTable(doc)
        keynote_table.LoadFrom(keynote_file_ref, None)
        t.Commit()
        print("[{}] Tabela de nota-chave recarregada".format(doc.Title))

    except Exception:
        traceback.print_exc()


def visit_link(app, value, visit_queue, visited, keynote_file_ref):
    open_options = OpenOptions()
    model_path = value["model_path"]
    try:
        linked_document = app.OpenDocumentFile(model_path, open_options)
        print("Abrindo: {}".format(linked_document.Title))
        visit_queue = read_links(linked_document, visit_queue, visited)
        reload_keynote_table(linked_document, keynote_file_ref)
        print("Fechando: {}".format(linked_document.Title))
        linked_document.Close()

    except Exception:
        traceback.print_exc()

    return visit_queue


def proccess_queue(visit_queue, visited):
    while visit_queue:
        path, value = visit_queue.popitem()
        visit_queue = visit_link(app, value, visit_queue, visited, keynote_file_ref)
        visited.append(path)


uidoc = __revit__.ActiveUIDocument
doc = uidoc.Document
app = __revit__.Application

keynote_file = forms.pick_file(file_ext="txt", title="Select keynote table file")
if not keynote_file:
    forms.alert("No keynote table file selected.", exitscript=True)

model_path = ModelPathUtils.ConvertUserVisiblePathToModelPath(keynote_file)
keynote_file_ref = ExternalResourceReference.CreateLocalResource(
    doc,
    ExternalResourceTypes.BuiltInExternalResourceTypes.KeynoteTable,
    model_path,
    PathType.Absolute,
)

print("Start")

visit_queue = {}
unloaded = []
visited = []
try:
    unloaded, visit_queue = unload_links(doc, unloaded, visited)
    reload_keynote_table(doc, keynote_file_ref)
    proccess_queue(visit_queue, visited)
    for link in unloaded:
        link.Reload()
    print("POP!")
except Exception:
    traceback.print_exc()
