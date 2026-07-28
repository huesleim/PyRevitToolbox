from Autodesk.Revit.DB import FilteredElementCollector, RevitLinkType, Element
import traceback

uidoc = __revit__.ActiveUIDocument
doc = uidoc.Document
app = __revit__.Application


def validate_links():
    links = FilteredElementCollector(doc).OfClass(RevitLinkType).ToElements()
    valid_links = []
    for link in links:
        keynote_ref = link.GetExternalFileReference()
        path = keynote_ref.GetAbsolutePath()

        linked_status = keynote_ref.GetLinkedFileStatus()
        if linked_status.ToString() == 'NotFound' or link.IsNestedLink:
            continue
        else:
            linked_document = app.OpenDocumentFile(path, None)
            keynote_table = linked_document.GetKeynoteTable()
            keynote_table.Reload()
            linked_document.Save()
            linked_document.Close()
        
        
#check if links are top tier
#for loop opening links
#checks if there is keynote table loaded
#reloads
#saves
#closes
#reloads links