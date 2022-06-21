import * as Panel from './panel';

import {Spec as BooleanSpec} from './PanelBoolean';
import {Spec as IdCompareSpec} from './PanelIdCompare';
import {Spec as IdCompareCountSpec} from './PanelIdCompareCount';
import {Spec as IdCountSpec} from './PanelIdCount';
import {Spec as TypeSpec} from './PanelType';
import {Spec as DateSpec} from './PanelDate';
import {Spec as NumberSpec} from './PanelNumber';
import {Spec as StringSpec} from './PanelString';
import {Spec as LinkSpec} from './PanelLink';
import {Spec as NullSpec} from './PanelNull';
import {Spec as StringHistogramSpec} from './PanelStringHistogram';
import {Spec as MultiStringHistogramSpec} from './PanelMultiStringHistogram';
import {Spec as BarChartSpec} from './PanelBarChart';
import {Spec as HistogramSpec} from './PanelHistogram';
import {Spec as PlotSpec} from './PanelPlot';
import {Spec as FacetSpec} from './PanelFacet';
// import {Spec as LayoutContainerSpec} from './PanelLayoutContainer';
// import {Spec as VariablesSpec} from './PanelVariables';
import {Spec as MultiHistogramSpec} from './PanelMultiHistogram';
import {Spec as UnknownSpec} from './PanelUnknown';
import {Spec as ImageSpec} from './PanelImage';
import {Spec as ImageCompareSpec} from './PanelImageCompare';
import {Spec as VideoSpec} from './PanelVideo';
import {Spec as AudioSpec} from './PanelAudio';
import {Spec as HTMLSpec} from './PanelHTML';
import {Spec as BokehSpec} from './PanelBokeh';
import {Spec as Object3DSpec} from './PanelObject3D';
import {Spec as MoleculeSpec} from './PanelMolecule';
import {Spec as SavedModelSpec} from './PanelSavedModel';

import {Spec as ObjectSpec} from './PanelObject';
import {Spec as ProjectOverviewSpec} from './PanelProjectOverview';
import {Spec as RunOverviewSpec} from './PanelRunOverview';
import {Spec as RunColorSpec} from './PanelRunColor';
import {Spec as PanelArtifactVersionAliasesSpec} from './PanelArtifactVersionAliases';

import {TableSpec} from './PanelTable/PanelTable';

import {Spec as StringCompare} from './PanelStringCompare';

// files
import {Spec as FileTextSpec} from './PanelFileText';
import {Spec as FileTextDiffSpec} from './PanelFileTextDiff';
import {Spec as FileMarkdownSpec} from './PanelFileMarkdown';
import {Spec as FileRawImageSpec} from './PanelFileRawImage';
import {Spec as FileJupyterSpec} from './PanelFileJupyter';
import {Spec as DirSpec} from './PanelDir';
import {Spec as NetronSpec} from './PanelNetron';
import {Spec as TraceSpec} from './PanelTrace';
import {Spec as WebVizSpec} from './PanelWebViz';

import {Spec as NDArraySpec} from './PanelNDArray';

// converters
import {Spec as RowSpec} from './PanelRow';
import {Spec as WBObjectSpec} from './PanelWBObject';
import {Spec as MaybeSpec} from './PanelMaybe';
// import {Spec as NumberToTimestampSpec} from './PanelNumberToTimestamp';

import {Spec as MultiTableSpec2} from './PanelTableMerge';
import {Spec as ProjectionSpec} from './PanelProjectionConverter';
import {PanelTableConfig} from './PanelTable/config';

import {WeavePythonPanelSpecs} from './PanelRegistryWeavePython';

// TODO: Wrap Panel components with makeSpec calls

// These are the all the registered panels. To register a new one, just add
// its spec here.
// The order of this array determines the default panel recommendation order.
// See scoreHandlerStack in availablePanels.ts for the function that
// determines the final order.

export type PanelSpecFunc = () => Panel.PanelSpec[];
export type ConverterSpecArray = Panel.PanelConvertSpec[];

// TODO(np): Lazily populating `panelSpecs` to avoid use-before-init when
// this module is loaded from one of the specs it contains.  Need to clean
// this up as part of encapsulating panel registry.

const panelSpecs: Panel.PanelSpec[] = [
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

  // Organizational
  // LayoutContainerSpec,
  // VariablesSpec,
].concat(WeavePythonPanelSpecs);

export const PanelSpecs: PanelSpecFunc = () => {
  return [...panelSpecs];
};

// add a new panel to the registry
export const registerPanel = (spec: Panel.PanelSpec) => {
  const index = panelSpecs.findIndex(s => s.id === spec.id);
  if (index === -1) {
    panelSpecs.push(spec);
  } else {
    panelSpecs[index] = spec;
  }
};

export const ConverterSpecs: ConverterSpecArray = [
  RowSpec,
  WBObjectSpec,
  MaybeSpec,
  // NumberToTimestampSpec,
  Panel.toConvertSpec(MultiTableSpec2),
  Panel.toConvertSpec(ProjectionSpec),
];
