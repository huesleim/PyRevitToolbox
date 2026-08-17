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

#def check_if_reloaded():
def unload_links(doc):
    links = FilteredElementCollector(doc).OfClass(RevitLinkType).ToElements()
    print("Encontrados {} aquivos .rvt vinculados".format(len(links)))
    unloaded_links = []
    instance_filter = ElementClassFilter(RevitLinkInstance)
    for link in links:
        if link.IsNestedLink:
            continue
        has_instance = len(link.GetDependentElements(instance_filter)) > 0
        if not has_instance:
            continue
        print("Checking link:", Element.Name.GetValue(link))
        if link.IsLoaded:
            link.Unload(None)
            print("Unloaded!")
            unloaded_links.append(link)
    return unloaded_links

def reload_keynote_table(doc, links=None, visited=None):
    if visited is None:
        visited = set()

    root_links = links is not None

    if not root_links:
        links = FilteredElementCollector(doc).OfClass(RevitLinkType).ToElements()

    if len(links) == 0:
        print("Last link in branch! Reloading keynote on this file")

    for link in links:
        link_name = Element.Name.GetValue(link)
        link_file_ref = link.GetExternalFileReference()
        path = link_file_ref.GetAbsolutePath()
        path_str = ModelPathUtils.ConvertModelPathToUserVisiblePath(path).lower()

        if (
            link.IsNestedLink
            or path_str in visited
        ):
            continue

        else:
            visited.add(path_str)
            open_options = OpenOptions()
            try:
                if link.IsLoaded:
                    link.Unload(None)
                linked_document = app.OpenDocumentFile(path, open_options)
                print(
                    "Opened {} successfully. Now proceeding to open nested links".format(
                        link_name
                    )
                )
            except Exception:
                traceback.print_exc()
                print("Failed to open {}. Moving to next link".format(link_name))
                link.Reload()
                continue

            try:
                reload_keynote_table(linked_document, visited=visited)

            finally:
                linked_document.Close()
                if not root_links: 
                    link.Reload()

    try:
        print("DOC:", doc.PathName)
        print("TITLE:", doc.Title)
        print("IS LINKED:", doc.IsLinked)
        t = Transaction(doc, "Reload keynote table on current file")
        t.Start()
        keynote_table = KeynoteTable.GetKeynoteTable(doc)
        keynote_table.LoadFrom(keynote_file_ref, None)
        t.Commit()

    except Exception:
        traceback.print_exc()


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
print('Start')
unloaded_links = unload_links(doc)
print('Links unloaded')
reload_keynote_table(doc, unloaded_links)
print('All files had keynote tables reloaded')
for link in unloaded_links: link.Reload()

print("POP!")
