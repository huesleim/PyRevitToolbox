# -*- coding: utf-8 -*-
import traceback
from System import Guid
from pyrevit import forms
from Autodesk.Revit.DB import (
    Element,
    FailureProcessingResult,
    FilteredElementCollector,
    GroupLoadOptions,
    GroupType,
    IFailuresPreprocessor,
    ModelPathUtils,
    Transaction,
)

uidoc = __revit__.ActiveUIDocument
doc = uidoc.Document

LINKED_IMPORT_WARNING = Guid("bddb95be-3daa-45ac-bde8-61a8030106f9")


class SwallowLinkedImportWarning(IFailuresPreprocessor):
    def PreprocessFailures(self, failures_accessor):
        for failure in failures_accessor.GetFailureMessages():
            if failure.GetFailureDefinitionId().Guid == LINKED_IMPORT_WARNING:
                failures_accessor.DeleteWarning(failure)
        return FailureProcessingResult.Continue


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
                "Grupo '{}' ainda não possui referência externa. Deseja escolher um arquivo?".format(
                    name
                ),
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
            print("Grupo '{}' recarregado com sucesso.".format(name))
        except Exception as e:
            print("Falha ao recarregar o grupo '{}': {}".format(name, str(e)))


group_types = FilteredElementCollector(doc).OfClass(GroupType).ToElements()
name_to_type = {Element.Name.GetValue(g): g for g in group_types}

selected_names = forms.SelectFromList.show(
    list(name_to_type.keys()),
    title="Selecione os grupos a serem recarregados",
    multiselect=True,
)

if not selected_names:
    forms.alert("Nenhum grupo selecionado. O script será encerrado.", exitscript=True)

selected_groups = [name_to_type[name] for name in selected_names]

t = Transaction(doc, "Recarregar grupos selecionados")
try:
    options = t.GetFailureHandlingOptions()
    options.SetFailuresPreprocessor(SwallowLinkedImportWarning())
    t.SetFailureHandlingOptions(options)

    t.Start()
    reload_groups(selected_groups)
    t.Commit()

except Exception:
    t.RollBack()
    traceback.print_exc()
