import React from 'react';

import * as Panel2 from '../panel';
import {inputType} from './common';

export const Spec: Panel2.PanelSpec = {
  id: 'bokeh-file',
  displayName: 'Bokeh',
  Component: React.lazy(() => import('./Component')),
  inputType,
};
