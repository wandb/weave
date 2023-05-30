import React from 'react';

import * as Panel2 from '../panel';
import {inputType} from './common';

export const Spec: Panel2.PanelSpec = {
  id: 'PanelPlotly',
  // component: React.lazy(() => import('./pages/TestPage')),
  Component: React.lazy(() => import('./Component')),
  inputType,
};
