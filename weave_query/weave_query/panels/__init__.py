from weave_query.weave_query import context_state as _context_state

_loading_builtins_token = _context_state.set_loading_built_ins()

from weave_query.weave_query.panel import Panel as Panel
from weave_query.weave_query.panels.panel_auto import *

# basic
from weave_query.weave_query.panels.panel_basic import *

# top level board
from weave_query.weave_query.panels.panel_board import (
    Board as Board,
)
from weave_query.weave_query.panels.panel_board import (
    BoardPanel as BoardPanel,
)
from weave_query.weave_query.panels.panel_board import (
    BoardPanelLayout as BoardPanelLayout,
)
from weave_query.weave_query.panels.panel_card import Card as Card
from weave_query.weave_query.panels.panel_card import CardTab as CardTab
from weave_query.weave_query.panels.panel_color import Color as Color
from weave_query.weave_query.panels.panel_daterange import DateRange as DateRange

# domain
from weave_query.weave_query.panels.panel_domain import *
from weave_query.weave_query.panels.panel_dropdown import Dropdown as Dropdown
from weave_query.weave_query.panels.panel_dropdown import (
    DropdownConfig as DropdownConfig,
)
from weave_query.weave_query.panels.panel_each import Each as Each
from weave_query.weave_query.panels.panel_each_column import EachColumn as EachColumn

# special
from weave_query.weave_query.panels.panel_expression import *
from weave_query.weave_query.panels.panel_facet import Facet as Facet
from weave_query.weave_query.panels.panel_facet_tabs import FacetTabs as FacetTabs
from weave_query.weave_query.panels.panel_filter_editor import (
    FilterEditor as FilterEditor,
)
from weave_query.weave_query.panels.panel_function_editor import (
    FunctionEditor as FunctionEditor,
)
from weave_query.weave_query.panels.panel_function_editor import (
    FunctionEditorConfig as FunctionEditorConfig,
)
from weave_query.weave_query.panels.panel_group import (
    Group as Group,
)
from weave_query.weave_query.panels.panel_group import (
    GroupLayoutFlow as GroupLayoutFlow,
)
from weave_query.weave_query.panels.panel_group import (
    GroupPanel as GroupPanel,
)
from weave_query.weave_query.panels.panel_group import (
    GroupPanelLayout as GroupPanelLayout,
)
from weave_query.weave_query.panels.panel_grouping_editor import (
    GroupingEditor as GroupingEditor,
)

# Incomplete
from weave_query.weave_query.panels.panel_histogram import *
from weave_query.weave_query.panels.panel_html import PanelHtml as PanelHtml

# layout
from weave_query.weave_query.panels.panel_labeled_item import LabeledItem as LabeledItem

# legacy
from weave_query.weave_query.panels.panel_legacy import *
from weave_query.weave_query.panels.panel_markdown import PanelMarkdown as PanelMarkdown

# Non-standard editor (todo: update)
from weave_query.weave_query.panels.panel_object_picker import (
    ObjectPicker as ObjectPicker,
)
from weave_query.weave_query.panels.panel_object_picker import (
    ObjectPickerConfig as ObjectPickerConfig,
)
from weave_query.weave_query.panels.panel_plot import Plot as Plot
from weave_query.weave_query.panels.panel_plot import PlotConstants as PlotConstants
from weave_query.weave_query.panels.panel_plot import Series as Series

# sidebar specific
from weave_query.weave_query.panels.panel_query import (
    Query as Query,
)
from weave_query.weave_query.panels.panel_query import (
    QueryCondition as QueryCondition,
)
from weave_query.weave_query.panels.panel_query import (
    QueryConfig as QueryConfig,
)
from weave_query.weave_query.panels.panel_sections import Sections as Sections
from weave_query.weave_query.panels.panel_select import SelectEditor as SelectEditor
from weave_query.weave_query.panels.panel_select import (
    SelectEditorConfig as SelectEditorConfig,
)

# editors
from weave_query.weave_query.panels.panel_slider import Slider as Slider
from weave_query.weave_query.panels.panel_slider import SliderConfig as SliderConfig
from weave_query.weave_query.panels.panel_string import PanelString as PanelString
from weave_query.weave_query.panels.panel_string_editor import (
    StringEditor as StringEditor,
)
from weave_query.weave_query.panels.panel_table import ColumnDef as ColumnDef
from weave_query.weave_query.panels.panel_table import Table as Table
from weave_query.weave_query.panels.panel_table import TableColumn as TableColumn
from weave_query.weave_query.panels.panel_trace import Trace as Trace

# navigation
from weave_query.weave_query.panels.panel_weavelink import WeaveLink as WeaveLink

_context_state.clear_loading_built_ins(_loading_builtins_token)
