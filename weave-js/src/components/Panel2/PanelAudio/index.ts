import React from 'react';

import * as Panel2 from '../panel';
import {inputType} from './common';

export const Spec: Panel2.PanelSpec = {
  id: 'audio-file',
  icon: 'music-audio',
  Component: React.lazy(() => import('./Component')),
  inputType,
  displayName: 'Audio',
};
