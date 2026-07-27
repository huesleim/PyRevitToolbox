from Autodesk.Revit.DB import FilteredElementCollector, RevitLinkType, ModelPathUtils, Element
from pyrevit import forms
import traceback


uidoc = __revit__.ActiveUIDocument
doc = uidoc.Document



try:
    links_paths = {}
    links = FilteredElementCollector(doc).OfClass(RevitLinkType).ToElements()
    folder = forms.pick_folder()


    for link in links:
        name = Element.Name.GetValue(link)
        ref = link.GetExternalFileReference()
        resource_ref = link.GetExternalResourceReference()
        
        path = ref.GetAbsolutePath()
        readable_path = ModelPathUtils.ConvertModelPathToUserVisiblePath(path)

        links_paths[name] = readable_path

        for root, dirs, files in os.walk(folder):
            for d in dirs: 
                if 'OBSOLETOS' not in d:
                    dirs [:] = d

        for filename in files:
            if filename.lower().endswith('rvt'):
                if filename.lower() == name.lower():
                    full_path = os.path.join(root, filename)
                    link.LoadFrom(full_path, .)
                    


except Exception:
    traceback.print_exc()
