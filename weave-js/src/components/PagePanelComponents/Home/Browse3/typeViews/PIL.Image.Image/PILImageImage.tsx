import React from 'react';
import {AutoSizer} from 'react-virtualized';

import {LoadingDots} from '../../../../../LoadingDots';
import {NotApplicable} from '../../NotApplicable';
import {useWFHooks} from '../../pages/wfReactInterface/context';
import {ImageContentWithData} from '../Content/ImageView';
import {CustomWeaveTypePayload} from '../customWeaveType.types';

type PILImageImageTypePayload = CustomWeaveTypePayload<
  'PIL.Image.Image',
  {'image.jpg': string} | {'image.png': string} | {'image.webp': string}
>;

type PILImageImageProps = {
  entity: string;
  project: string;
  data: PILImageImageTypePayload;
};

export const PILImageImage = (props: PILImageImageProps) => (
  <AutoSizer style={{height: '100%', width: '100%'}}>
    {({width, height}) => {
      if (width === 0 || height === 0) {
        return null;
      }
      return (
        <PILImageImageWithSize
          {...props}
          containerWidth={width}
          containerHeight={height}
        />
      );
    }}
  </AutoSizer>
);

type PILImageImageWithSizeProps = PILImageImageProps & {
  containerWidth: number;
  containerHeight: number;
};

const PILImageImageWithSize = ({
  entity,
  project,
  data,
  containerWidth,
  containerHeight,
}: PILImageImageWithSizeProps) => {
  const {useFileContent} = useWFHooks();
  const imageTypes = {
    'image.jpg': 'image/jpeg',
    'image.png': 'image/png',
    'image.webp': 'image/webp',
  } as const;

  const imageKey = Object.keys(data.files).find(key => key in imageTypes) as
    | keyof PILImageImageTypePayload['files']
    | undefined;
  const imageBinary = useFileContent({
    entity,
    project,
    digest: imageKey ? data.files[imageKey] : '',
    skip: !imageKey,
  });
  if (!imageKey) {
    return <NotApplicable />;
  } else if (imageBinary.loading) {
    return <LoadingDots />;
  } else if (imageBinary.result == null) {
    return <span></span>;
  }
  const mimetype = imageTypes[imageKey as keyof typeof imageTypes];
  // Delegate to content representation

  return (
    <ImageContentWithData
      mimetype={mimetype}
      buffer={imageBinary.result}
      containerWidth={containerWidth}
      containerHeight={containerHeight}
    />
  );
};
