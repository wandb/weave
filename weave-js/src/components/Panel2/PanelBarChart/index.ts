import * as Panel2 from '../panel';
import {inputType} from './common';
import Component from './Component';

export const Spec: Panel2.PanelSpec = {
  id: 'barchart',
  displayName: 'Bar Chart',
  icon: 'chart-horizontal-bars',
  category: 'Data',
  Component,
  inputType,
  canFullscreen: true,

  defaultFixedSize: {
    width: 200,
    height: (9 / 16) * 200,
  },
};
