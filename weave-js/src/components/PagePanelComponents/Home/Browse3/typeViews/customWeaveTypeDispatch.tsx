import React from 'react';

import {CustomWeaveTypePayload} from './customWeaveType.types';
import {
  isPILImageImageType,
  PILImageImage,
} from './PIL.Image.Image/PILImageImage';

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
