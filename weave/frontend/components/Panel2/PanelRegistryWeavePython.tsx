// Panels specifically for Weave Python, these are not
// production ready, which is why we separate this file

import {Spec as RunSpec} from './PanelRun';
import {Spec as PanelAnyObj} from './PanelAnyObj';
import {Spec as PanelGpt3Model} from './PanelGpt3Model';
import {Spec as PanelStringEditor} from './PanelStringEditor';
import {Spec as PanelTextEditor} from './PanelTextEditor';
import {Spec as PanelPanel} from './PanelPanel';
import {Spec as PanelContainer} from './PanelContainer';
import {Spec as SliderSpec} from './PanelSlider';
import {Spec as PanelNewImage} from './PanelNewImage';
import {Spec as PanelStringHistogramWeave} from './PanelStringHistogramWeave';
import {Spec as PanelLabeledItem} from './PanelLabeledItem';
import {Spec as PanelGroup} from './PanelGroup';
import {Spec as PanelCard} from './PanelCard';

export const WeavePythonPanelSpecs = [
  RunSpec,
  PanelAnyObj,
  PanelGpt3Model,
  PanelStringEditor,
  PanelTextEditor,
  PanelPanel,
  PanelContainer,
  SliderSpec,
  PanelNewImage,
  PanelStringHistogramWeave,
  PanelLabeledItem,
  PanelGroup,
  PanelCard,
];
