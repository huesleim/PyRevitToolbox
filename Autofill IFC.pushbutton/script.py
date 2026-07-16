# -*- coding: utf-8 -*-
from Autodesk.Revit.Exceptions import OperationCanceledException
from Autodesk.Revit.DB import BuiltInCategory, Transaction, BuiltInParameter, SectionType, FilteredElementCollector, ElementId, ScheduleFieldType
import traceback

uidoc = __revit__.ActiveUIDocument
doc = uidoc.Document
schedule = doc.ActiveView
table = schedule.GetTableData()
body = table.GetSectionData(SectionType.Body)
t = Transaction(doc, "Autofill IFC") 
elements = list(FilteredElementCollector(doc, schedule.Id).ToElements())

def find_ifc_value(category, text):
    mapping = {
        int(BuiltInCategory.OST_Doors): "IfcDoor",
        int(BuiltInCategory.OST_Ceilings): "IfcCovering",
        int(BuiltInCategory.OST_Roofs): "IfcCovering",
        int(BuiltInCategory.OST_Stairs): "IfcStair",
        int(BuiltInCategory.OST_Windows): "IfcWindow",
        int(BuiltInCategory.OST_SpecialityEquipment): ("IfcDoor", "TRAPDOOR"),
        int(BuiltInCategory.OST_Railings): "IfcRailing",
        }

    if category == int(BuiltInCategory.OST_Walls):
        if 'rev' in text:
            return 'IfcCovering', 'CLADDING'
        elif 'rod' in text:
            return 'IfcCovering', 'SKIRTINGBOARD'
        elif 'div' in text:
            return 'IfcWall', 'PARTITIONING'
        elif 'conc' in text:
            return 'IfcWall', 'SOLIDWALL'
        elif 'alv' in text and 'est' in text:
            return 'IfcWall', None
        elif 'pele' in text:
            return 'IfcCurtainWall', None
        elif 'alambrado' in text or 'grade' in text:
            return 'IfcRailing'
        else: 
            return 'IfcWall', 'STANDARD'

    elif category == int(BuiltInCategory.OST_Floors):
        if 'sol' in text or 'fil' in text:
            return 'IfcCovering', 'USERDEFINED'
        elif 'rodape' in text:
            return 'IfcCovering', 'SKIRTINGBOARD'
        elif 'rev' in text:
            return 'IfcCovering', 'FLOORING'

    else: 
        return mapping.get(category, None)


t.Start()

definition = schedule.Definition
definition.IsItemized = True

for row in range(body.NumberOfRows):
    elem = elements[row]
    text = schedule.GetCellText(SectionType.Body, row, 0).lower()
    category = elem.Category.Id.IntegerValue
    value = find_ifc_value(category, text)

    if value:
        if isinstance(value, (list, tuple)):
            first_value = value[0]
            second_value = value[1] if len(value) > 1 else None
        else:
            first_value = value
            second_value = None

        firstParam = elem.get_Parameter(BuiltInParameter.IFC_EXPORT_ELEMENT_AS)
        if firstParam and not firstParam.IsReadOnly:
            firstParam.Set(first_value)
            print("Row {}: {} -> {}".format(row, text, first_value))

        secondParam = elem.get_Parameter(BuiltInParameter.IFC_EXPORT_PREDEFINEDTYPE)
        if secondParam and not secondParam.IsReadOnly:
            if second_value is not None:
                secondParam.Set(second_value)
                print("Row {}: {} -> {}".format(row, text, second_value))

definition.IsItemized = False

t.Commit()



# except OperationCanceledException:
#     print("Selection cancelled.")

# except Exception:
#     traceback.print_exc()

#     ifc_mapping = {
#         'portão de ferro entrada de veículos': 'IfcDoorGATE',
#         'tampos, bancadas e balcões': 'IfcFurnishingElementUSERDEFINED',
#         'brise metálico': 'IfcShadingDeviceUSERDEFINED',
#         'escada marinheiro': 'IfcStair',
#         'plataforma de transferência': 'IfcTransportUSERDEFINED',
#     }




