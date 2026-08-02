from Autodesk.Revit.DB import FilteredElementCollector, RevitLinkType, ModelPathUtils, Element
from pyrevit import forms
import traceback, os
uidoc = __revit__.ActiveUIDocument
doc = uidoc.Document

def walk_folder(folder):
    files_path = {}
    for root, dirs, files in os.walk(folder):
        dirs [:] = [d for d in dirs if 'obsoletos' not in d.lower() and 'backup' not in d.lower()]
        for filename in files:
            if filename.lower().endswith('.rvt'):
                full_path = os.path.join(root, filename)
                files_path[filename.lower()] = full_path
    return files_path 

try:
    links_paths = {}
    links = FilteredElementCollector(doc).OfClass(RevitLinkType).ToElements()
    folder = forms.pick_folder()
    print ('Selected folder: {}'.format(folder))
    if not folder:
        forms.alert('No folder selected.', exitscript=True)

    files_path = walk_folder(folder)

    for link in links:
        name = Element.Name.GetValue(link)
        name_lower = name.lower()
        print ('Commencing reload for link: {}'.format(name))

        ref = link.GetExternalFileReference()
        path = ref.GetAbsolutePath()
        readable_path = ModelPathUtils.ConvertModelPathToUserVisiblePath(path)

        links_paths[name] = readable_path

        full_path = files_path.get(name_lower)
        if not full_path:
            print ('Could not find a matching file for {}. Skipping...'.format(name_lower))
            continue

        model_path = ModelPathUtils.ConvertUserVisiblePathToModelPath(files_path[name_lower])

        link.LoadFrom(model_path, None)
        print ('Reloaded {} from {}'.format(name, full_path))


except Exception:
    traceback.print_exc()
    
