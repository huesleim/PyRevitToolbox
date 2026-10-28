# -*- coding: utf-8 -*-

# ---------------------------------------------------------------------------- #
#                                    IMPORTS                                   #
# ---------------------------------------------------------------------------- #

import os

import re

import clr
import helpers
import System
import traceback

from Autodesk.Revit.DB import (
    BuiltInCategory,
    BuiltInParameter,
    ColorDepthType,
    DWGExportOptions,
    Element,
    ElementId,
    ExportPaperFormat,
    FilteredElementCollector,
    PageOrientationType,
    PaperPlacementType,
    PDFExportOptions,
    PDFExportQualityType,
    RasterQualityType,
    TableCellCombinedParameterData,
    ViewSheet,
    ZoomType,
)

from System.Collections.Generic import List
from pyrevit import forms, script

# ---------------------------------------------------------------------------- #
#                                   FUNCTIONS                                  #
# ---------------------------------------------------------------------------- #

# combo name -> (PDFExportOptions property, enum type)
ENUM_COMBOS = {
    "cmb_paper_format": ("PaperFormat", ExportPaperFormat),
    "cmb_orientation": ("PaperOrientation", PageOrientationType),
    "cmb_placement": ("PaperPlacement", PaperPlacementType),
    "cmb_zoom_type": ("ZoomType", ZoomType),
    "cmb_color_depth": ("ColorDepth", ColorDepthType),
    "cmb_export_quality": ("ExportQuality", PDFExportQualityType),
    "cmb_raster_quality": ("RasterQuality", RasterQualityType),
}

ENUM_DEFAULTS = {
    "cmb_paper_format": "ISO_A1",
    "cmb_orientation": "Landscape",
    "cmb_placement": "Center",
    "cmb_zoom_type": "Zoom",
    "cmb_color_depth": "Color",
    "cmb_export_quality": "DPI4000",
    "cmb_raster_quality": "Presentation",
}

NAMING_PARTS = [
    ("project", "Disciplina (Sigla)", "", ""),
    ("project", "Número do projeto", "-", ""),
    # ("project", "Etapa", "-", ""),
    ("sheet", BuiltInParameter.SHEET_NUMBER, "-", ""),
    ("sheet", BuiltInParameter.SHEET_NAME, "-", ""),
    ("sheet", BuiltInParameter.SHEET_CURRENT_REVISION, "-", ""),
]


class ExportWindow(forms.WPFWindow):
    def __init__(self):
        forms.WPFWindow.__init__(self, XAML_PATH)
        self.result = None  # PDFExportOptions, set on confirm
        self.folder = None  # destination folder, set on confirm

        # fill the enum dropdowns
        for combo_name, (_, enum_type) in ENUM_COMBOS.items():
            combo = getattr(self, combo_name)
            names = list(System.Enum.GetNames(clr.GetClrType(enum_type)))
            combo.ItemsSource = names
            default = ENUM_DEFAULTS.get(combo_name)
            combo.SelectedIndex = names.index(default) if default in names else 0

        self.on_combine_changed(None, None)
        self.on_placement_changed(None, None)
        self.on_zoom_type_changed(None, None)

    # enable/disable dependent fields
    def on_combine_changed(self, sender, args):
        self.txt_filename.IsEnabled = bool(self.chk_combine.IsChecked)

    def on_placement_changed(self, sender, args):
        offset = self.cmb_placement.SelectedItem not in (None, "Center")
        self.txt_offset_x.IsEnabled = offset
        self.txt_offset_y.IsEnabled = offset

    def on_zoom_type_changed(self, sender, args):
        self.txt_zoom.IsEnabled = self.cmb_zoom_type.SelectedItem == "Zoom"

    # buttons
    def on_browse(self, sender, args):
        folder = forms.pick_folder(title="Selecione a pasta de destino")
        if folder:
            self.txt_folder.Text = folder

    def on_cancel(self, sender, args):
        self.Close()

    def on_ok(self, sender, args):
        try:
            offset_x = float(self.txt_offset_x.Text.replace(",", "."))
            offset_y = float(self.txt_offset_y.Text.replace(",", "."))
            zoom = int(self.txt_zoom.Text)
        except ValueError:
            forms.alert("Deslocamentos e zoom devem ser numericos.")
            return
        if not self.txt_folder.Text:
            forms.alert("Selecione a pasta de destino.")
            return

        opts = PDFExportOptions()
        opts.Combine = bool(self.chk_combine.IsChecked)
        if opts.Combine:
            opts.FileName = self.txt_filename.Text
        else:
            rule = build_naming_rule(NAMING_PARTS)
            if rule is None:
                return
            if not PDFExportOptions.IsValidNamingRule(rule):
                forms.alert("Regra de nomenclatura inválida!")
                return
            opts.SetNamingRule(rule)

        opts.OriginOffsetX = offset_x / 304.8  # mm -> ft
        opts.OriginOffsetY = offset_y / 304.8
        opts.ZoomPercentage = zoom
        opts.AlwaysUseRaster = bool(self.chk_always_raster.IsChecked)
        opts.HideCropBoundaries = bool(self.chk_hide_crop.IsChecked)
        opts.HideReferencePlane = bool(self.chk_hide_refplane.IsChecked)
        opts.HideScopeBoxes = bool(self.chk_hide_scopebox.IsChecked)
        opts.HideUnreferencedViewTags = bool(self.chk_hide_unref_tags.IsChecked)
        opts.MaskCoincidentLines = bool(self.chk_mask_coincident.IsChecked)
        opts.ReplaceHalftoneWithThinLines = bool(self.chk_halftone_thin.IsChecked)
        opts.ViewLinksInBlue = bool(self.chk_view_links_blue.IsChecked)
        opts.StopOnError = bool(self.chk_stop_on_error.IsChecked)
        opts.SetExportInBackground(False)

        # enums: convert the selected name back to the enum member
        for combo_name, (prop, enum_type) in ENUM_COMBOS.items():
            selected = getattr(self, combo_name).SelectedItem
            setattr(opts, prop, getattr(enum_type, selected))

        self.folder = self.txt_folder.Text
        self.result = opts
        self.Close()


def build_name_string(parts, sheet):
    pieces = []
    for source, key, prefix, suffix in parts:
        param = (
            doc.ProjectInformation.LookupParameter(key)
            if source == "project"
            else sheet.get_Parameter(key)
        )
        if param is None:
            forms.alert("Parâmetro não encontrado: {}".format(key))
            return None
        value = param.AsString() or param.AsValueString()
        if value:  # empty values are skipped, with their prefix and suffix
            pieces.append((prefix if pieces else "") + value + suffix)
    return re.sub(r'[\\/:*?"<>|]', "_", "".join(pieces))


def build_naming_rule(parts):
    rule = []
    for source, key, prefix, suffix in parts:
        if source == "project":
            param = doc.ProjectInformation.LookupParameter(key)
            if param is None:
                forms.alert("Parâmetro de projeto não encontrado: {}".format(key))
                return None
            category, param_id = BuiltInCategory.OST_ProjectInformation, param.Id
        else:
            category, param_id = BuiltInCategory.OST_Sheets, ElementId(key)
        item = TableCellCombinedParameterData.Create()
        item.CategoryId = ElementId(category)
        item.ParamId = param_id
        item.Prefix = prefix
        item.Suffix = suffix
        rule.append(item)
    return rule


# ---------------------------------------------------------------------------- #
#                                   VARIABLES                                  #
# ---------------------------------------------------------------------------- #

uidoc = __revit__.ActiveUIDocument
doc = uidoc.Document
app = __revit__.Application
XAML_PATH = os.path.join(os.path.dirname(__file__), "export_window.xaml")


target_sheets = FilteredElementCollector(doc).OfClass(ViewSheet).ToElements()
name_to_elem = {
    "{} - {}".format(e.SheetNumber, Element.Name.GetValue(e)): e for e in target_sheets
}
selected_elements = forms.SelectFromList.show(
    sorted(name_to_elem.keys()),
    title="Escolha as pranchas a serem exportadas",
    multiselect=True,
)
if not selected_elements:
    forms.alert("Nenhuma vista selecionada", exitscript=True)


result = forms.CommandSwitchWindow.show(
    ["Exportar"], 
    switches=["PDF", "DWG"], 
    message="Selecione os formatos a exportar",
)
if not result or not result[0]:
    script.exit()

selection, switches = result
export_pdf = switches["PDF"]
export_dwg = switches["DWG"]

view_ids = List[ElementId]([name_to_elem[name].Id for name in selected_elements])

window = ExportWindow()
window.show_dialog()
if window.result is None:
    script.exit()
pdf_settings = window.result

dwg_settings = DWGExportOptions.GetPredefinedOptions(doc, "DWG")
if dwg_settings is None:
    forms.alert(
        "Configuração de exportação 'DWG' não encontrada no projeto.", exitscript=True
    )



# ---------------------------------------------------------------------------- #
#                                     MAIN                                     #
# ---------------------------------------------------------------------------- #
try:
    if export_pdf:
        doc.Export(window.folder, view_ids, pdf_settings)

    if export_dwg:
        sheets = [name_to_elem[name] for name in selected_elements]
        for sheet in sheets:
            dwg_name = build_name_string(NAMING_PARTS, sheet)
            if dwg_name is None:
                script.exit()
            ok = doc.Export(
                window.folder, dwg_name, List[ElementId]([sheet.Id]), dwg_settings
            )
            if not ok:
                print("Falha ao exportar DWG: {}".format(dwg_name))

except Exception:
    traceback.print_exc()

forms.alert("Exportação concluída!")
os.startfile(window.folder)
