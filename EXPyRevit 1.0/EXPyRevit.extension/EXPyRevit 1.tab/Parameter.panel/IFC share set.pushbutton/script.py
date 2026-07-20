# -*- coding: utf-8 -*-
from Autodesk.Revit.Exceptions import OperationCanceledException
from Autodesk.Revit.DB import BuiltInCategory, Transaction, BuiltInParameter, SectionType, FilteredElementCollector, ElementId, ScheduleFieldType
import traceback

# Select elements and declare variables #
uidoc = __revit__.ActiveUIDocument
doc = uidoc.Document
schedule = doc.ActiveView
table = schedule.GetTableData()
body = table.GetSectionData(SectionType.Body)
t = Transaction(doc, 'Autofill IFC') 
elements = list(FilteredElementCollector(doc, schedule.Id).ToElements())

# Function to find the appropriate IFC value based on category and text #
def find_ifc_value(category, text):
    text = text.lower() if text else ''
    mapping = {
        int(BuiltInCategory.OST_Doors): "IfcDoor",
        int(BuiltInCategory.OST_Ceilings): "IfcCovering",
        int(BuiltInCategory.OST_Roofs): "IfcCovering",
        int(BuiltInCategory.OST_Stairs): "IfcStair",
        int(BuiltInCategory.OST_Windows): "IfcWindow",
        int(BuiltInCategory.OST_SpecialityEquipment): ("IfcDoor", "TRAPDOOR"),
        int(BuiltInCategory.OST_StairsRailing): "IfcRailing",
        int(BuiltInCategory.OST_Railings): "IfcRailing",
        int(BuiltInCategory.OST_Casework): ("IfcFurnishingElement", "USERDEFINED"),
    }
    
    if category ==int(BuiltInCategory.OST_MechanicalEquipment):
        if 'elevador' in text in text:
            return 'IfcSpace'
    
    if category ==int(BuiltInCategory.OST_SpecialityEquipment):
        if 'alçapão' in text or 'trapdoor' in text:
            return 'IfcDoor', 'TRAPDOOR'    
        elif 'portão' in text:
            return 'IfcDoor', 'GATE'
        elif 'escada' in text:
            return 'IfcStair'
        
    if category == int(BuiltInCategory.OST_Walls):
        if 'rev' in text:
            return 'IfcCovering', 'CLADDING'
        elif 'rod' in text:
            return 'IfcCovering', 'SKIRTINGBOARD'
        elif 'div' in text:
            return 'IfcWall', 'PARTITIONING'
        elif 'conc' in text or ('osso' in text and 'gesso' not in text):
            return 'IfcWall', 'SOLIDWALL'
        elif 'alv' in text and 'est' in text:
            return 'IfcWall'
        elif 'pele' in text:
            return 'IfcCurtainWall'
        elif 'alambrado' in text or 'grade' in text:
            return 'IfcRailing'
        else: 
            return 'IfcWall', 'STANDARD'

    elif category == int(BuiltInCategory.OST_Floors):
        if 'sol' in text or 'exp-fil' in text:
            return 'IfcCovering', 'USERDEFINED'
        elif 'rodape' in text:
            return 'IfcCovering', 'SKIRTINGBOARD'
        elif 'rev' in text:
            return 'IfcCovering', 'FLOORING'
        elif 'radier' in text or 'laje' in text:
            return 
        else: 
            return 'IfcCovering', 'FLOORING'

    elif category == int(BuiltInCategory.OST_CurtainWallPanels):
        if 'portão' in text:
            return 'IfcDoor', 'GATE'
        if 'porta' in text:
            return 'IfcDoor', 'USERDEFINED'
        if 'alambrado' in text:
            return 'IfcRailing'
    else: 
        return mapping.get(category, None)


t.Start()

definition = schedule.Definition
definition.IsItemized = False
try: 
    for i, elem in enumerate(elements):
        familyAndType = elem.get_Parameter(BuiltInParameter.ELEM_FAMILY_AND_TYPE_PARAM) 
        text = familyAndType.AsValueString() if familyAndType else ''
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
            if firstParam and not firstParam.IsReadOnly and first_value is not None:
                firstParam.Set(first_value)

            secondParam = elem.get_Parameter(BuiltInParameter.IFC_EXPORT_PREDEFINEDTYPE)
            if secondParam and not secondParam.IsReadOnly and second_value is not None:
                secondParam.Set(second_value)

    t.Commit()
    print('Na Victa é assim! :p')



except OperationCanceledException:
    print('Selection cancelled.')
    t.Rollback()

except Exception:
    traceback.print_exc()
    t.RollBack()