import React from 'react';

import {LoadingDots} from '../../../../../LoadingDots';
import {useWFHooks} from '../../pages/wfReactInterface/context';
import {CustomWeaveTypePayload} from '../customWeaveType.types';

type PILImageImageTypePayload = CustomWeaveTypePayload<
  'PIL.Image.Image',
  {'image.png': string}
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
  const {useFileContent} = useWFHooks();
  const imageBinary = useFileContent(
    props.entity,
    props.project,
    props.data.files['image.png']
  );

  if (imageBinary.loading) {
    return <LoadingDots />;
  } else if (imageBinary.result == null) {
    return <span></span>;
  }

  const arrayBuffer = imageBinary.result as any as ArrayBuffer;
  const blob = new Blob([arrayBuffer], {type: 'image/png'});
  const url = URL.createObjectURL(blob);

  // TODO: It would be nice to have a more general image render - similar to the
  // ValueViewImage that does things like light box, general scaling,
  // downloading, etc..
  return (
    <img
      src={url}
      alt="Custom"
      style={{
        maxWidth: '100%',
        maxHeight: '100%',
      }}
    />
  );
};
