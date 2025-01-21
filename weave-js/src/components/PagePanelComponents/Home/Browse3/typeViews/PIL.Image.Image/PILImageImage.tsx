import React, {useEffect, useMemo, useState} from 'react';
import {AutoSizer} from 'react-virtualized';
import Lightbox from 'yet-another-react-lightbox';
import Fullscreen from 'yet-another-react-lightbox/plugins/fullscreen';
import Zoom from 'yet-another-react-lightbox/plugins/zoom';

import {StyledTooltip, TooltipHint} from '../../../../../DraggablePopups';
import {LoadingDots} from '../../../../../LoadingDots';
import {NotApplicable} from '../../NotApplicable';
import {useWFHooks} from '../../pages/wfReactInterface/context';
import {CustomWeaveTypePayload} from '../customWeaveType.types';

type PILImageImageTypePayload = CustomWeaveTypePayload<
  'PIL.Image.Image',
  {'image.jpg': string} | {'image.png': string}
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
    'image.jpg': 'jpg',
    'image.png': 'png',
  } as const;

  const imageKey = Object.keys(data.files).find(key => key in imageTypes) as
    | keyof PILImageImageTypePayload['files']
    | undefined;
  const imageBinary = useFileContent(
    entity,
    project,
    imageKey ? data.files[imageKey] : '',
    {skip: !imageKey}
  );
  if (!imageKey) {
    return <NotApplicable />;
  } else if (imageBinary.loading) {
    return <LoadingDots />;
  } else if (imageBinary.result == null) {
    return <span></span>;
  }
  const fileExt = imageTypes[imageKey as keyof typeof imageTypes];

  return (
    <PILImageImageWithData
      fileExt={fileExt}
      buffer={imageBinary.result}
      containerWidth={containerWidth}
      containerHeight={containerHeight}
    />
  );
};

const loadImage = (setImageDim: any, imageUrl: string) => {
  const img = new Image();
  img.src = imageUrl;

  img.onload = () => {
    setImageDim({
      height: img.height,
      width: img.width,
    });
  };
  img.onerror = err => {
    console.log('img error');
    console.error(err);
  };
};

type PILImageImageWithDataProps = {
  fileExt: 'jpg' | 'png';
  buffer: ArrayBuffer;
  containerWidth: number;
  containerHeight: number;
};

const PILImageImageWithData = ({
  fileExt,
  buffer,
  containerWidth,
  containerHeight,
}: PILImageImageWithDataProps) => {
  const url = useMemo(() => {
    const blob = new Blob([buffer], {
      type: `image/${fileExt}`,
    });
    return URL.createObjectURL(blob);
  }, [buffer, fileExt]);

  const [imageDim, setImageDim] = useState({
    width: -1,
    height: -1,
  });
  useEffect(() => {
    setImageDim({width: -1, height: -1});
    loadImage(setImageDim, url);
  }, [url]);

  if (imageDim.width === -1 || imageDim.height === -1) {
    return <LoadingDots />;
  }
  return (
    <PILImageImageLoaded
      url={url}
      fileExt={fileExt}
      imageWidth={imageDim.width}
      imageHeight={imageDim.height}
      containerWidth={containerWidth}
      containerHeight={containerHeight}
    />
  );
};

type PILImageImageLoadedProps = {
  url: string;
  fileExt: 'jpg' | 'png';
  imageWidth: number;
  imageHeight: number;
  containerWidth: number;
  containerHeight: number;
};

const previewWidth = 300;
const previewHeight = 300;

const PILImageImageLoaded = ({
  url,
  fileExt,
  imageWidth,
  imageHeight,
  containerWidth,
  containerHeight,
}: PILImageImageLoadedProps) => {
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const onClick = () => setLightboxOpen(true);

  let image = (
    <img
      style={{
        maxWidth: '100%',
        maxHeight: '100%',
        cursor: 'pointer',
      }}
      src={url}
      alt="Custom"
      onClick={onClick}
    />
  );

  const hasPreview =
    containerWidth < previewWidth || containerHeight < previewHeight;

  if (hasPreview) {
    const preview = (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          cursor: 'pointer',
        }}>
        <div
          style={{
            maxWidth: previewWidth,
            maxHeight: previewHeight,
            margin: 'auto',
          }}>
          <img
            style={{
              maxWidth: '100%',
              maxHeight: '100%',
            }}
            src={url}
            alt="Custom"
            onClick={onClick}
          />
        </div>
        <TooltipHint>
          {imageWidth}x{imageHeight}, {fileExt} - Click for more details
        </TooltipHint>
      </div>
    );
    image = (
      <StyledTooltip enterDelay={500} title={preview}>
        {image}
      </StyledTooltip>
    );
  }

  return (
    <>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100%',
        }}>
        {image}
      </div>
      <Lightbox
        plugins={[Fullscreen, Zoom]}
        open={lightboxOpen}
        close={() => setLightboxOpen(false)}
        controller={{
          closeOnBackdropClick: true,
        }}
        slides={[{src: url}]}
        render={{
          // Hide previous and next buttons because we only have one image.
          buttonPrev: () => null,
          buttonNext: () => null,
        }}
        carousel={{finite: true}}
      />
    </>
  );
};
