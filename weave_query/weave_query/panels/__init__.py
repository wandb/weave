from weave_query import context_state as _context_state

_loading_builtins_token = _context_state.set_loading_built_ins()

from weave_query.panels.panel_auto import *

# basic
from weave_query.panels.panel_basic import *

# top level board
from weave_query.panels.panel_board import Board, BoardPanel, BoardPanelLayout
from weave_query.panels.panel_card import Card, CardTab
from weave_query.panels.panel_color import Color
from weave_query.panels.panel_daterange import DateRange

# domain
from weave_query.panels.panel_domain import *
from weave_query.panels.panel_dropdown import Dropdown, DropdownConfig
from weave_query.panels.panel_each import Each
from weave_query.panels.panel_each_column import EachColumn

# special
from weave_query.panels.panel_expression import *
from weave_query.panels.panel_facet import Facet
from weave_query.panels.panel_facet_tabs import FacetTabs
from weave_query.panels.panel_filter_editor import FilterEditor
from weave_query.panels.panel_function_editor import (
    FunctionEditor,
    FunctionEditorConfig,
)
from weave_query.panels.panel_group import (
    Group,
    GroupLayoutFlow,
    GroupPanel,
    GroupPanelLayout,
)
from weave_query.panels.panel_grouping_editor import GroupingEditor

# Incomplete
from weave_query.panels.panel_histogram import *
from weave_query.panels.panel_html import PanelHtml

# layout
from weave_query.panels.panel_labeled_item import LabeledItem

# legacy
from weave_query.panels.panel_legacy import *
from weave_query.panels.panel_markdown import PanelMarkdown

# Non-standard editor (todo: update)
from weave_query.panels.panel_object_picker import ObjectPicker, ObjectPickerConfig
from weave_query.panels.panel_plot import Plot, PlotConstants, Series

# sidebar specific
from weave_query.panels.panel_query import Query, QueryCondition, QueryConfig
from weave_query.panels.panel_sections import Sections
from weave_query.panels.panel_select import SelectEditor, SelectEditorConfig

# editors
from weave_query.panels.panel_slider import Slider, SliderConfig
from weave_query.panels.panel_string import PanelString
from weave_query.panels.panel_string_editor import StringEditor
from weave_query.panels.panel_table import ColumnDef, Table, TableColumn
from weave_query.panels.panel_trace import Trace

# navigation
from weave_query.panels.panel_weavelink import WeaveLink
from weave_query.panel import Panel

_context_state.clear_loading_built_ins(_loading_builtins_token)
