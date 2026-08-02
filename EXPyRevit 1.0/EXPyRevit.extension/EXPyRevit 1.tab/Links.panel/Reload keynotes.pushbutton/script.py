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
    PathType
)

from pyrevit import forms
import traceback

uidoc = __revit__.ActiveUIDocument
doc = uidoc.Document
app = __revit__.Application

keynote_file = forms.pick_file(file_ext='txt', title='Select keynote table file')
if not keynote_file:
    forms.alert('No keynote table file selected.', exitscript=True)

model_path = ModelPathUtils.ConvertUserVisiblePathToModelPath(keynote_file)
keynote_file_ref = ExternalResourceReference.CreateLocalResource(
    doc,
    ExternalResourceTypes.BuiltInExternalResourceTypes.KeynoteTable,
    model_path,
    PathType.Absolute,
)

links = FilteredElementCollector(doc).OfClass(RevitLinkType).ToElements()
if len(links) == 0:
    print('There are no linked revit files!')


for link in links:
    link_name = Element.Name.GetValue(link)
    link_file_ref = link.GetExternalFileReference()
    path = link_file_ref.GetAbsolutePath()
    linked_status = link_file_ref.GetLinkedFileStatus()

    if linked_status.ToString() == 'NotFound' or linked_status.ToString() == 'Unloaded' or link.IsNestedLink or link.IsLoaded == False:
        continue

    else:
        open_options = OpenOptions()
        link.Unload(None)
        try:
            linked_document = app.OpenDocumentFile(path, open_options)
            print('Opened {} successfully. Now proceeding to reload keynote table'.format(link_name))
        except Exception:
            traceback.print_exc()
            print('Failed to open {}. Moving to next link'.format(link_name))
            link.Reload()
            continue

        try:
            keynote_table = KeynoteTable.GetKeynoteTable(linked_document)
            link_transaction = Transaction(linked_document, 'test')
            link_transaction.Start()
            keynote_table.LoadFrom(keynote_file_ref, None)
            link_transaction.Commit()
            print('Keynote table reloaded successfully in linked file.')

        except Exception:
            traceback.print_exc()
            if link_transaction.HasStarted():
                link_transaction.RollBack()

        finally:
            linked_document.Close()
            link.Reload()


try:
    t = Transaction(doc, 'Reload keynote table on current file')
    t.Start()
    keynote_table = KeynoteTable.GetKeynoteTable(doc)
    keynote_table.LoadFrom(keynote_file_ref, None)
    t.Commit()
    print('Na Victa eh assim! :p')

except Exception:
    traceback.print_exc()
        
