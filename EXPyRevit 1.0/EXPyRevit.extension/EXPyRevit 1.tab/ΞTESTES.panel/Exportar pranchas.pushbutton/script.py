
# -*- coding: utf-8 -*-

# ---------------------------------------------------------------------------- #
#                                    IMPORTS                                   #
# ---------------------------------------------------------------------------- #

import os
import clr
import helpers
import System
from pyrevit import forms, script
from Autodesk.Revit.DB import (
    BuiltInCategory,
    BuiltInParameter,
    ColorDepthType,
    DWGExportOptions,
    Element,
    ElementId,
    FilteredElementCollector,
    PDFExportQualityType,
    RasterQualityType,
    ExportPaperFormat,
    PageOrientationType,
    PaperPlacementType,
    PDFExportOptions,
    TableCellCombinedParameterData,
    ZoomType,
    ViewSheet
)



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

NAMING_PARTS = [
    (BuiltInParameter.SHEET_NUMBER, "", ""),
    (BuiltInParameter.SHEET_NAME, "-", ""),
    (BuiltInParameter.SHEET_CURRENT_REVISION, "-", ""),
]

class ExportWindow(forms.WPFWindow):
    def __init__(self):
        forms.WPFWindow.__init__(self, XAML_PATH)
        self.result = None  # PDFExportOptions, set on confirm
        self.folder = None  # destination folder, set on confirm

        # fill the enum dropdowns
        for combo_name, (_, enum_type) in ENUM_COMBOS.items():
            combo = getattr(self, combo_name)
            combo.ItemsSource = list(System.Enum.GetNames(clr.GetClrType(enum_type)))
            combo.SelectedIndex = 0

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
            if not PDFExportOptions.IsValidNamingRule(rule):
                forms.alert("Regra de nomenclatura inválida!")
                return
            opts.SetNamingRule(rule)
            
        opts.OriginOffsetX = offset_x / 304.8  # mm -> feet
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

def build_naming_rule(parts):
    rule = []
    for bip, prefix, suffix in parts:
        item = TableCellCombinedParameterData.Create()
        item.CategoryId = ElementId(BuiltInCategory.OST_Sheets)
        item.ParamId = ElementId(bip)
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
name_to_elem = {"{} - {}".format(e.SheetNumber, Element.Name.GetValue(e)): e for e in target_sheets}
selected_elements = forms.SelectFromList.show(
    list(name_to_elem.keys()),
    title="Escolha as pranchas a serem exportadas",
    multiselect=True,
)
if not selected_elements:
    forms.alert("Nenhuma vista selecionada", exitscript=True)

view_ids = [name_to_elem[name].Id for name in selected_elements]

print (view_ids)

window = ExportWindow()
window.show_dialog()
if window.result is None:
    script.exit()
pdf_settings = window.result


# ---------------------------------------------------------------------------- #
#                                     MAIN                                     #
# ---------------------------------------------------------------------------- #

print ("Iniciando exportação")

doc.Export(window.folder, view_ids, pdf_settings)

forms.alert("Exportação concluída!")
os.open(window.folder)