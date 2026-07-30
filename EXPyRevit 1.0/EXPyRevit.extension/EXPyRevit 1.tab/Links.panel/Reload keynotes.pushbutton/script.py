from Autodesk.Revit.DB import FilteredElementCollector, RevitLinkType, OpenOptions, KeynoteTable, Transaction, Element, LinkedFileStatus
import traceback

uidoc = __revit__.ActiveUIDocument
doc = uidoc.Document
app = __revit__.Application


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
            print('Opened {} successfully. Now proceeding to open transaction'.format(link_name))
        except Exception:
            traceback.print_exc()
            print('Failed to open {}. Moving to next link'.format(link_name))
            link.Reload()
            continue

        try:
            keynote_table = KeynoteTable.GetKeynoteTable(linked_document)
            keynote_table_file_ref = keynote_table.GetExternalFileReference()
            keynote_table_linked_status = keynote_table_file_ref.GetLinkedFileStatus()

            if keynote_table_linked_status.ToString() == 'NotFound':
                print('{}\'s keynote table file path is broken'.format(link_name))
                continue
            link_transaction = Transaction(linked_document, 'test')
            link_transaction.Start()
            keynote_table.Reload(None)
            link_transaction.Commit()

            linked_document.Save()
            print('Keynote table reloaded successfully in linked file.')

        except Exception:
            traceback.print_exc()
            if link_transaction.HasStarted():
                link_transaction.RollBack()

        finally:
            link.Reload()
            linked_document.Close()


try:
    t = Transaction(doc, 'Reload keynote table on current file')
    t.Start()
    keynote_table = KeynoteTable.GetKeynoteTable(doc)
    keynote_table.Reload(None)
    t.Commit()
    print('Na Victa eh assim! :p')

except Exception:
    traceback.print_exc()
        
