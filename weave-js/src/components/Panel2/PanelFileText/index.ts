import React from 'react';

import * as Panel2 from '../panel';
import {inputType} from './common';

export {EXTENSION_INFO, processTextForDisplay} from './common';

export const Spec: Panel2.PanelSpec = {
  id: 'text',
  Component: React.lazy(() => import('./Component')),
  inputType,
};
