# -*- coding: utf-8 -*-
import traceback
from pyrevit import forms
from Autodesk.Revit.DB import (
    BuiltInCategory,
    Element,
    ElementId,
    FilteredElementCollector,
    GroupLoadOptions,
    GroupType,
    LinkElementId,
    ModelPathUtils,
    OpenOptions,
    RevitLinkInstance,
    Transaction,
    UV,
    ViewType,
)

uidoc = __revit__.ActiveUIDocument
doc = uidoc.Document
current_view = uidoc.ActiveView

def reload_groups(selected_groups):
    group_options = GroupLoadOptions()
    group_options.IncludeAttachedDetails = False
    group_options.IncludeLevels = False

    for group in selected_groups:
        name = Element.Name.GetValue(group)
        if group.IsExternalFileReference(): 
            external_reference = group.GetExternalFileReference()
            path = external_reference.GetAbsolutePath()
            path = ModelPathUtils.ConvertModelPathToUserVisiblePath(path)
        
        else:
            wants_file = forms.alert(
                "Grupo '{}' ainda não possui referência externa. Deseja escolher um arquivo?".format(name),
                yes=True,
                no=True,
    )
            
            if not wants_file:
                continue

            path = forms.pick_file(file_ext="rvt")
            if not path:
                continue

        try:
            group.LoadFrom(path, group_options)
            print("Grupo '{}' recarregado com sucesso.".format(group.Name))
        except Exception as e:
            print("Falha ao recarregar o grupo '{}': {}".format(group.Name, str(e)))



group_types = FilteredElementCollector(doc).OfClass(GroupType).ToElements()
name_to_type = {Element.Name.GetValue(g): g for g in group_types}
print (name_to_type)

selected_groups = forms.SelectFromList.show(
    list(name_to_type.keys()),
    title="Selecione os grupos a serem recarregados",
    multiselect=True
    )

selected_groups = [name_to_type[name] for name in selected_groups]

print ("selected_groups: {}".format(selected_groups))

if not selected_groups:
    forms.alert("Nenhum grupo selecionado. O script será encerrado.", exitscript=True
)

t = Transaction (doc, "Recarregar grupos selecionados")
try:
    t.Start()
    reload_groups(selected_groups)
    t.Commit()

except Exception:
    t.RollBack()
    traceback.print_exc()
