// Panels specifically for Weave Python, these are not
// production ready, which is why we separate this file

import {Spec as PanelAnyObj} from './PanelAnyObj';
import {Spec as PanelCard} from './PanelCard';
import {Spec as PanelColor} from './PanelColor';
import {Spec as PanelDateRange} from './PanelDateRange';
// import {Spec as PanelSelectEditor} from './PanelSelectEditor';
import {Spec as PanelDropdown} from './PanelDropdown';
import {Spec as PanelLayoutFlow} from './PanelEach';
import {Spec as PanelEachColumn} from './PanelEachColumn';
import {Spec as PanelFacetTabs} from './PanelFacetTabs';
import {Spec as PanelFilterEditor} from './PanelFilterEditor';
import {Spec as PanelFunctionEditor} from './PanelFunctionEditor';
// import {Spec as PanelAuto} from './PanelAuto';
import {Spec as PanelGpt3Model} from './PanelGpt3Model';
import {Spec as PanelGroup} from './PanelGroup';
import {Spec as PanelGroupingEditor} from './PanelGroupingEditor';
import {Spec as PanelHexColor} from './PanelHexColor';
import {Spec as PanelLabeledItem} from './PanelLabeledItem';
import {Spec as PanelNewImage} from './PanelNewImage';
import {Spec as PanelObjectPicker} from './PanelObjectPicker';
import {Spec as PanelOpDef} from './PanelOpDef';
import {Spec as PanelPanel} from './PanelPanel';
import {Spec as PanelPlotly} from './PanelPlotly';
import {Spec as PanelQuery} from './PanelQuery';
import {Spec as PanelRef} from './PanelRef';
import {Spec as RunSpec} from './PanelRun';
import {Spec as PanelSections} from './PanelSections';
import {Spec as PanelSlider} from './PanelSlider';
import {Spec as PanelStringEditor} from './PanelStringEditor';
import {Spec as PanelStringHistogramWeave} from './PanelStringHistogramWeave';
import {Spec as PanelTextEditor} from './PanelTextEditor';
import {Spec as PanelWeaveLink} from './PanelWeaveLink';

export const weavePythonPanelSpecs = () => {
  return [
    RunSpec,
    PanelAnyObj,
    // PanelAuto doesn't route config updates correctly and breaks stuff.
    // Don't need it yet anyway
    // PanelAuto,
    PanelGpt3Model,
    PanelStringEditor,
    PanelTextEditor,
    // PanelSelectEditor,
    PanelDropdown,
    PanelFilterEditor,
    PanelGroupingEditor,
    PanelDateRange,
    PanelPanel,
    PanelSlider,
    PanelRef,
    PanelObjectPicker,
    PanelQuery,
    PanelFunctionEditor,
    PanelNewImage,
    PanelStringHistogramWeave,
    PanelLabeledItem,
    PanelEachColumn,
    PanelGroup,
    PanelCard,
    PanelWeaveLink,
    PanelPlotly,
    PanelColor,
    PanelHexColor,
    PanelLayoutFlow,
    PanelFacetTabs,
    PanelSections,
    PanelOpDef,
  ];
};
