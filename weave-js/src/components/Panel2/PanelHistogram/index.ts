import * as Panel2 from '../panel';
import {inputType} from './common';
import Component from './Component';
import ConfigComponent from './ConfigComponent';

export const Spec: Panel2.PanelSpec = {
  id: 'histogram',
  ConfigComponent,
  Component,
  inputType,
  canFullscreen: true,
};
