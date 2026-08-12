from Autodesk.Revit.DB import (
    ModelPathUtils,
    FilteredElementCollector,
    RevitLinkType,
    OpenOptions,
    KeynoteTable,
    Transaction,
    Element,
    LinkedFileStatus,
    ExternalResourceReference,
    ExternalResourceTypes,
    PathType,
)

from pyrevit import forms
import traceback


def reload_keynote_table(doc, visited=None):
    if visited is None:
        visited = set()

    links = FilteredElementCollector(doc).OfClass(RevitLinkType).ToElements()

    if len(links) == 0:
        print("Last link in branch! Reloading keynote on this file")

    for link in links:
        link_name = Element.Name.GetValue(link)
        link_file_ref = link.GetExternalFileReference()
        path = link_file_ref.GetAbsolutePath()
        linked_status = link_file_ref.GetLinkedFileStatus()
        path_str = ModelPathUtils.ConvertModelPathToUserVisiblePath(path).lower()

        if (
            linked_status.ToString() == "NotFound"
            or linked_status.ToString() == "Unloaded"
            or link.IsNestedLink
            or link.IsLoaded == False
            or path_str in visited
        ):
            continue

        else:
            visited.add(path_str)
            open_options = OpenOptions()
            link.Unload(None)
            try:
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
                reload_keynote_table(linked_document, visited)

            finally:
                linked_document.Close()
                link.Reload()

    try:
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

reload_keynote_table(doc)
print("POP!")
