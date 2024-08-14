import React from 'react';

import {CustomWeaveTypePayload} from './customWeaveType.types';
import {
  isPILImageImageType,
  PILImageImage,
} from './PIL.Image.Image/PILImageImage';

/**
 * This is the primary entry-point for dispatching custom weave types. Currently
 * we just have 1, but as we add more, we might want to add a more robust
 * "registry"
 */
export const customWeaveTypeDispatch = (
  entity: string,
  project: string,
  data: CustomWeaveTypePayload
) => {
  if (isPILImageImageType(data)) {
    return <PILImageImage entity={entity} project={project} data={data} />;
  }

  return null;
};
