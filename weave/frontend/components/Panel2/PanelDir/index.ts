import * as Panel2 from '../panel';
import React from 'react';
import {inputType} from './common';

export const Spec: Panel2.PanelSpec = {
  id: 'dir',
  displayName: 'Directory',
  Component: React.lazy(() => import('./Component')),
  inputType,
};
