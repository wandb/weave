import * as Panel2 from '../panel';
import * as PComp from './component';
import * as POp from './op';
import * as PTypes from './types';

export const Spec: Panel2.PanelSpec = {
  id: 'projection',
  displayName: '2D Projection',
  Component: PComp.PanelProjectionConverter,
  ConfigComponent: PComp.PanelProjectionConverterConfig,
  inputType: PTypes.inputType,
  outputType: POp.outputType,
  equivalentTransform: POp.equivalentTransform,
};

Panel2.registerPanelFunction(
  Spec.id,
  Spec.inputType,
  Spec.equivalentTransform!
);
