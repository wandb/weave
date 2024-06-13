from weave import context_state as _context_state

_loading_builtins_token = _context_state.set_loading_built_ins()

from weave.panel import Panel
from weave.panels.panel_auto import *

# basic
from weave.panels.panel_basic import *

# top level board
from weave.panels.panel_board import Board, BoardPanel, BoardPanelLayout
from weave.panels.panel_card import Card, CardTab
from weave.panels.panel_color import Color
from weave.panels.panel_daterange import DateRange

# domain
from weave.panels.panel_domain import *
from weave.panels.panel_dropdown import Dropdown, DropdownConfig
from weave.panels.panel_each import Each
from weave.panels.panel_each_column import EachColumn

# special
from weave.panels.panel_expression import *
from weave.panels.panel_facet import Facet
from weave.panels.panel_facet_tabs import FacetTabs
from weave.panels.panel_filter_editor import FilterEditor
from weave.panels.panel_function_editor import FunctionEditor, FunctionEditorConfig
from weave.panels.panel_group import (
    Group,
    GroupLayoutFlow,
    GroupPanel,
    GroupPanelLayout,
)
from weave.panels.panel_grouping_editor import GroupingEditor

# Incomplete
from weave.panels.panel_histogram import *
from weave.panels.panel_html import PanelHtml

# layout
from weave.panels.panel_labeled_item import LabeledItem

# legacy
from weave.panels.panel_legacy import *
from weave.panels.panel_markdown import PanelMarkdown

# Non-standard editor (todo: update)
from weave.panels.panel_object_picker import ObjectPicker, ObjectPickerConfig
from weave.panels.panel_plot import Plot, PlotConstants, Series

# sidebar specific
from weave.panels.panel_query import Query, QueryCondition, QueryConfig
from weave.panels.panel_sections import Sections
from weave.panels.panel_select import SelectEditor, SelectEditorConfig

# editors
from weave.panels.panel_slider import Slider, SliderConfig
from weave.panels.panel_string import PanelString
from weave.panels.panel_string_editor import StringEditor
from weave.panels.panel_table import ColumnDef, Table, TableColumn
from weave.panels.panel_trace import Trace

# navigation
from weave.panels.panel_weavelink import WeaveLink

_context_state.clear_loading_built_ins(_loading_builtins_token)
