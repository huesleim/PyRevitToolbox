# -*- coding: utf-8 -*-
from Autodesk.Revit.DB import FilteredElementCollector, RevitLinkType, ModelPathUtils, Element
from pyrevit import forms
import os

import helpers
from helpers import log, print_error

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
    if not folder:
        forms.alert('Nenhuma pasta selecionada.', exitscript=True)
    log('Pasta selecionada: {}'.format(folder))

    files_path = walk_folder(folder)

    for link in links:
        if link.IsNestedLink:
            continue
        name = Element.Name.GetValue(link)
        name_lower = name.lower()
        log('Iniciando recarregamento do vínculo: {}'.format(name))

        ref = link.GetExternalFileReference()
        path = ref.GetAbsolutePath()
        readable_path = ModelPathUtils.ConvertModelPathToUserVisiblePath(path)

        links_paths[name] = readable_path

        full_path = files_path.get(name_lower)
        if not full_path:
            log('Não foi possível encontrar um arquivo correspondente para {}. Ignorando...'.format(name_lower))
            continue

        model_path = ModelPathUtils.ConvertUserVisiblePathToModelPath(files_path[name_lower])

        link.LoadFrom(model_path, None)
        log('{} recarregado a partir de {}'.format(name, full_path))


except Exception:
    print_error('Falha ao procurar links')
    
#18 - 27