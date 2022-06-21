import * as Panel2 from '../panel';
import React from 'react';
import {inputType} from './common';
export {EMPTY_EXPRESSION_PANEL} from './common';
export type {PanelExpressionConfig} from './common';

export const Spec: Panel2.PanelSpec = {
  id: 'expression',
  Component: React.lazy(() => import('./Component')),
  inputType,
  canFullscreen: true,

  defaultFixedSize: {
    width: 200,
    height: (9 / 16) * 200,
  },
};
