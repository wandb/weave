import React from 'react';

import * as Panel2 from '../panel';
import {inputType} from './common';
import {defaultFacet} from './common';

export {defaultFacet} from './common';

export const Spec: Panel2.PanelSpec = {
  id: 'Facet',

  initialize: (weave, inputNode) => defaultFacet(),

  ConfigComponent: React.lazy(() =>
    import('./Component').then(module => ({default: module.PanelFacetConfig}))
  ),

  Component: React.lazy(() => import('./Component')),
  inputType,
  hidden: true,
};
