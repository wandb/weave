import {IconName} from '../Icon';
import * as Panel from './panel';
import {Spec as PanelArtifactVersionAliasesSpec} from './PanelArtifactVersionAliases';
import {Spec as PanelArtifactVersionTagsSpec} from './PanelArtifactVersionTags';
import {Spec as AudioSpec} from './PanelAudio';
import {Spec as BarChartSpec} from './PanelBarChart';
import {Spec as BokehSpec} from './PanelBokeh';
import {Spec as BooleanSpec} from './PanelBoolean';
import {Spec as DateSpec} from './PanelDate';
import {Spec as DirSpec} from './PanelDir';
import {Spec as ExprSpec} from './PanelExpr';
import {Spec as ExpressionGraph} from './PanelExpressionGraph';
import {Spec as FacetSpec} from './PanelFacet';
import {Spec as FileJupyterSpec} from './PanelFileJupyter';
import {Spec as FileMarkdownSpec} from './PanelFileMarkdown';
import {Spec as FileRawImageSpec} from './PanelFileRawImage';
import {Spec as FileTextSpec} from './PanelFileText';
import {Spec as FileTextDiffSpec} from './PanelFileTextDiff';
import {Spec as HistogramSpec} from './PanelHistogram';
import {Spec as HTMLSpec} from './PanelHTML';
import {Spec as IdCompareSpec} from './PanelIdCompare';
import {Spec as IdCompareCountSpec} from './PanelIdCompareCount';
import {Spec as IdCountSpec} from './PanelIdCount';
import {Spec as ImageSpec} from './PanelImage';
import {Spec as ImageCompareSpec} from './PanelImageCompare';
import {PanelCategory} from './panellib/types';
import {Spec as LinkSpec} from './PanelLink';
import {Spec as MaybeSpec} from './PanelMaybe';
import {Spec as MoleculeSpec} from './PanelMolecule';
// import {Spec as VariablesSpec} from './PanelVariables';
import {Spec as MultiHistogramSpec} from './PanelMultiHistogram';
import {Spec as MultiStringHistogramSpec} from './PanelMultiStringHistogram';
import {Spec as NDArraySpec} from './PanelNDArray';
import {Spec as NetronSpec} from './PanelNetron';
import {Spec as NullSpec} from './PanelNull';
import {Spec as NumberSpec} from './PanelNumber';
import {Spec as ObjectSpec} from './PanelObject';
import {Spec as Object3DSpec} from './PanelObject3D';
import {Spec as PlotSpec} from './PanelPlot/PanelPlot';
import {Spec as PrecomputedHistogramSpec} from './PanelPrecomputedHistogram';
import {Spec as ProjectionSpec} from './PanelProjectionConverter';
import {Spec as ProjectOverviewSpec} from './PanelProjectOverview';
import {Spec as RawFallbackSpec} from './PanelRawFallback';
import {weavePythonPanelSpecs} from './PanelRegistryWeavePython';
// converters
import {Spec as RowSpec} from './PanelRow';
import {Spec as RunColorSpec} from './PanelRunColor';
import {Spec as RunOverviewSpec} from './PanelRunOverview';
import {Spec as PanelRunsTableSpec} from './PanelRunsTable';
import {Spec as SavedModelSpec} from './PanelSavedModel';
import {Spec as StringSpec} from './PanelString';
import {Spec as StringCompare} from './PanelStringCompare';
import {Spec as StringHistogramSpec} from './PanelStringHistogram';
import {TableSpec} from './PanelTable/PanelTable';
// import {Spec as NumberToTimestampSpec} from './PanelNumberToTimestamp';
import {Spec as MultiTableSpec2} from './PanelTableMerge';
import {Spec as TraceSpec} from './PanelTrace';
import {Spec as PanelTraceSpec} from './PanelTraceTree/PanelTrace';
import {Spec as PanelTraceSpanSpec} from './PanelTraceTree/PanelTraceSpan';
import {Spec as PanelTraceSpanModelSpec} from './PanelTraceTree/PanelTraceSpanModel';
import {Spec as PanelTraceTreeFromHistoryTraceTableViewerSpec} from './PanelTraceTree/PanelTraceTreeFromHistoryTableViewer';
import {Spec as TraceTreeModelSpec} from './PanelTraceTree/PanelTraceTreeModel';
import {Spec as PanelTraceTreeTraceTableViewerSpec} from './PanelTraceTree/PanelTraceTreeTableViewer';
import {Spec as TraceTreeTraceSpec} from './PanelTraceTree/PanelTraceTreeTrace';
import {Spec as TypeSpec} from './PanelType';
import {Spec as UnknownSpec} from './PanelUnknown';
import {Spec as VideoSpec} from './PanelVideo';
import {Spec as WBObjectSpec} from './PanelWBObject';
import {Spec as WebVizSpec} from './PanelWebViz';

// TODO: Wrap Panel components with makeSpec calls

// These are all the registered panels. To register a new one, just add
// its spec here.
// The order of this array determines the default panel recommendation order.
// See scoreHandlerStack in availablePanels.ts for the function that
// determines the final order.

export type PanelSpecFunc = () => Panel.PanelSpec[];
export type ConverterSpecArray = Panel.PanelConvertSpec[];

// TODO(np): Lazily populating `panelSpecs` to avoid use-before-init when
// this module is loaded from one of the specs it contains.  Need to clean
// this up as part of encapsulating panel registry.

let panelSpecs: Panel.PanelSpec[] = [];

const panelIdToIcon: Record<string, IconName> = {};
const panelIdToCategory: Record<string, PanelCategory> = {};

const initSpecs = () => {
  if (panelSpecs.length === 0) {
    panelSpecs = [
      ExprSpec,
      // RootBrowserSpec,

      IdCompareSpec,
      IdCompareCountSpec,
      IdCountSpec,

      TypeSpec,
      DateSpec,
      BooleanSpec,

      // arrays
      TableSpec,
      PlotSpec,
      FacetSpec,

      // numbers
      NumberSpec,
      BarChartSpec,
      HistogramSpec,
      PrecomputedHistogramSpec,
      MultiHistogramSpec,

      // strings
      StringSpec,
      StringCompare,
      StringHistogramSpec,
      MultiStringHistogramSpec,

      // Do we still need these?
      NullSpec,
      UnknownSpec,

      // explicit links
      LinkSpec,

      // Objects
      ObjectSpec,

      // WB Objects
      ProjectOverviewSpec,
      RunOverviewSpec,
      RunColorSpec,

      // other files
      ImageSpec,
      ImageCompareSpec,
      FileJupyterSpec,
      FileRawImageSpec,
      FileMarkdownSpec,
      FileTextDiffSpec,
      FileTextSpec,
      NetronSpec,
      TraceSpec,
      WebVizSpec,
      VideoSpec,
      AudioSpec,
      HTMLSpec,
      BokehSpec,
      Object3DSpec,
      MoleculeSpec,
      SavedModelSpec,

      // directories
      DirSpec,

      NDArraySpec,

      PanelArtifactVersionAliasesSpec,
      PanelArtifactVersionTagsSpec,

      PanelTraceTreeTraceTableViewerSpec,
      PanelTraceTreeFromHistoryTraceTableViewerSpec,
      TraceTreeTraceSpec,
      TraceTreeModelSpec,
      PanelTraceSpec,
      PanelTraceSpanSpec,
      PanelTraceSpanModelSpec,

      RawFallbackSpec,

      // Organizational
      // LayoutContainerSpec,
      // VariablesSpec,
      ExpressionGraph,
    ].concat(weavePythonPanelSpecs());
  }

  // Initialize panel id to icon and category mapping
  for (const spec of panelSpecs) {
    if (spec.icon) {
      panelIdToIcon[spec.id] = spec.icon;
    }
    if (spec.category) {
      panelIdToCategory[spec.id] = spec.category;
    }
  }
};

export const PanelSpecs: PanelSpecFunc = () => {
  initSpecs();
  return [...panelSpecs];
};

// add a new panel to the registry
export const registerPanel = (spec: Panel.PanelSpec) => {
  initSpecs();
  const index = panelSpecs.findIndex(s => s.id === spec.id);
  if (index === -1) {
    panelSpecs.push(spec);
  } else {
    panelSpecs[index] = spec;
  }

  // Update panel id mappings
  if (spec.icon) {
    panelIdToIcon[spec.id] = spec.icon;
  } else {
    delete panelIdToIcon[spec.id];
  }
  if (spec.category) {
    panelIdToCategory[spec.id] = spec.category;
  } else {
    delete panelIdToCategory[spec.id];
  }
};

export const getPanelIcon = (panelId: string): IconName => {
  return panelIdToIcon[panelId] ?? 'panel';
};
export const getPanelCategory = (panelId: string): PanelCategory => {
  return panelIdToCategory[panelId] ?? 'Other';
};

let converterSpecs: ConverterSpecArray = [];
export const ConverterSpecs = (): ConverterSpecArray =>
  converterSpecs.length > 0
    ? converterSpecs
    : (converterSpecs = [
        RowSpec,
        WBObjectSpec,
        MaybeSpec,
        // NumberToTimestampSpec,
        Panel.toConvertSpec(MultiTableSpec2),
        Panel.toConvertSpec(ProjectionSpec),
        Panel.toConvertSpec(PanelRunsTableSpec),
      ]);
