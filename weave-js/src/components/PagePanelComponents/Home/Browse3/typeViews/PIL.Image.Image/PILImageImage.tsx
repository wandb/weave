import React from 'react';

import {LoadingDots} from '../../../../../LoadingDots';
import {useWFHooks} from '../../pages/wfReactInterface/context';
import {CustomWeaveTypePayload} from '../customWeaveType.types';

type PILImageImageTypePayload = CustomWeaveTypePayload<
  'PIL.Image.Image',
  {'image.jpg': string} | {'image.png': string}
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

  const imageTypes = {
    'image.jpg': 'jpg',
    'image.png': 'png',
  } as const;

  const imageKey = Object.keys(props.data.files).find(
    key => key in imageTypes
  ) as keyof PILImageImageTypePayload['files'];
  if (!imageKey) {
    return <span>Img not found!</span>;
  }

  const imageBinary = useFileContent(
    props.entity,
    props.project,
    props.data.files[imageKey]
  );
  const imageFileExt = imageTypes[imageKey as keyof typeof imageTypes];

  if (imageBinary.loading) {
    return <LoadingDots />;
  } else if (imageBinary.result == null) {
    return <span></span>;
  }

  const arrayBuffer = imageBinary.result as any as ArrayBuffer;
  const blob = new Blob([arrayBuffer], {
    type: `image/${imageFileExt}`,
  });
  const url = URL.createObjectURL(blob);

  // TODO: It would be nice to have a more general image render - similar to the
  // ValueViewImage that does things like light box, general scaling,
  // downloading, etc..
  return (
    <img
      src={url}
      alt="Custom"
      style={{
        width: '100%',
        height: '100%',
        objectFit: 'contain',
      }}
    />
  );
};
