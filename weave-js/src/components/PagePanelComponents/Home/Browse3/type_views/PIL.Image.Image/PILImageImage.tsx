import React from 'react';

import {useWFHooks} from '../../pages/wfReactInterface/context';
import {CustomWeaveTypePayload} from '../customWeaveType.types';

type PILImageImageTypePayload = CustomWeaveTypePayload<
  'PIL.Image.Image',
  {'image.py': string}
>;

export const isPILImageImageType = (
  data: CustomWeaveTypePayload
): data is PILImageImageTypePayload => {
  return data.weave_type.type === 'PIL.Image.Image';
};

export const PILImageImage: React.FC<{
  entity: string;
  project: string;
  data: PILImageImageTypePayload;
}> = props => {
  //   const {useFileContent} = useWFHooks();
  //   const image_binary = useFileContent(props.data.files['image.py']);
  //   image_binary;
  return <>Image</>;
};
