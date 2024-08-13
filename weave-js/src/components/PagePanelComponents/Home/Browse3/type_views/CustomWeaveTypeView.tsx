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

// export const customWeaveTypeHasDispatch = (
//   data: CustomWeaveTypePayload
// ): boolean => {
//   return isPILImageImageType(data);
// };

// export const CustomWeaveTypeView: React.FC<{
//   data: CustomWeaveTypePayload;
// }> = props => {
//   const typeId = props.data.weave_type.type;
//   const dispatch = customWeaveTypeDispatch(props.data);
//   if (dispatch) {
//     return dispatch;
//   }

//   return <span>CustomWeaveType: {typeId}</span>;
// };
