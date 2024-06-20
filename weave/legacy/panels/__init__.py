from weave.legacy import context_state as _context_state

_loading_builtins_token = _context_state.set_loading_built_ins()

from weave.legacy.panels.panel_auto import *

# basic
from weave.legacy.panels.panel_basic import *

# top level board
from weave.legacy.panels.panel_board import Board, BoardPanel, BoardPanelLayout
from weave.legacy.panels.panel_card import Card, CardTab
from weave.legacy.panels.panel_color import Color
from weave.legacy.panels.panel_daterange import DateRange

# domain
from weave.legacy.panels.panel_domain import *
from weave.legacy.panels.panel_dropdown import Dropdown, DropdownConfig
from weave.legacy.panels.panel_each import Each
from weave.legacy.panels.panel_each_column import EachColumn

# special
from weave.legacy.panels.panel_expression import *
from weave.legacy.panels.panel_facet import Facet
from weave.legacy.panels.panel_facet_tabs import FacetTabs
from weave.legacy.panels.panel_filter_editor import FilterEditor
from weave.legacy.panels.panel_function_editor import (
    FunctionEditor,
    FunctionEditorConfig,
)
from weave.legacy.panels.panel_group import (
    Group,
    GroupLayoutFlow,
    GroupPanel,
    GroupPanelLayout,
)
from weave.legacy.panels.panel_grouping_editor import GroupingEditor

# Incomplete
from weave.legacy.panels.panel_histogram import *
from weave.legacy.panels.panel_html import PanelHtml

# layout
from weave.legacy.panels.panel_labeled_item import LabeledItem

# legacy
from weave.legacy.panels.panel_legacy import *
from weave.legacy.panels.panel_markdown import PanelMarkdown

# Non-standard editor (todo: update)
from weave.legacy.panels.panel_object_picker import ObjectPicker, ObjectPickerConfig
from weave.legacy.panels.panel_plot import Plot, PlotConstants, Series

# sidebar specific
from weave.legacy.panels.panel_query import Query, QueryCondition, QueryConfig
from weave.legacy.panels.panel_sections import Sections
from weave.legacy.panels.panel_select import SelectEditor, SelectEditorConfig

# editors
from weave.legacy.panels.panel_slider import Slider, SliderConfig
from weave.legacy.panels.panel_string import PanelString
from weave.legacy.panels.panel_string_editor import StringEditor
from weave.legacy.panels.panel_table import ColumnDef, Table, TableColumn
from weave.legacy.panels.panel_trace import Trace

# navigation
from weave.legacy.panels.panel_weavelink import WeaveLink
from weave.legacy.panel import Panel

_context_state.clear_loading_built_ins(_loading_builtins_token)
