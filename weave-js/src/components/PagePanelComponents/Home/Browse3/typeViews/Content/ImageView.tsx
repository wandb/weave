import {StyledTooltip} from '@wandb/weave/components/DraggablePopups';
import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import {NotApplicable} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/NotApplicable';
import {useWFHooks} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/context';
import {ContentViewMetadataLoadedProps} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/typeViews/Content/types';
import React, {useEffect, useMemo, useState} from 'react';
import {AutoSizer} from 'react-virtualized';
import Lightbox from 'yet-another-react-lightbox';
import Fullscreen from 'yet-another-react-lightbox/plugins/fullscreen';
import Zoom from 'yet-another-react-lightbox/plugins/zoom';

export const ImageContent = (props: ContentViewMetadataLoadedProps) => (
  <AutoSizer style={{height: '100%', width: '100%'}}>
    {({width, height}) => {
      if (width === 0 || height === 0) {
        return null;
      }
      return (
        <ImageContentWithSize
          {...props}
          containerWidth={width}
          containerHeight={height}
        />
      );
    }}
  </AutoSizer>
);

type ImageContentWithSizeProps = ContentViewMetadataLoadedProps & {
  containerWidth: number;
  containerHeight: number;
};

const ImageContentWithSize = ({
  entity,
  project,
  content,
  metadata,
  containerWidth,
  containerHeight,
}: ImageContentWithSizeProps) => {
  const {useFileContent} = useWFHooks();
  const imageBinary = useFileContent({
    entity,
    project,
    digest: content,
    skip: !content,
  });
  if (!content) {
    return <NotApplicable />;
  } else if (imageBinary.loading) {
    return <LoadingDots />;
  } else if (imageBinary.result == null) {
    return <span></span>;
  }

  return (
    <ImageContentWithData
      mimetype={metadata.mimetype}
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

type ImageContentWithDataProps = {
  mimetype: string;
  buffer: ArrayBuffer;
  containerWidth: number;
  containerHeight: number;
};

export const ImageContentWithData = ({
  mimetype,
  buffer,
  containerWidth,
  containerHeight,
}: ImageContentWithDataProps) => {
  const url = useMemo(() => {
    const blob = new Blob([buffer], {
      type: mimetype,
    });
    return URL.createObjectURL(blob);
  }, [buffer, mimetype]);

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
    <ImageContentLoaded
      url={url}
      imageWidth={imageDim.width}
      imageHeight={imageDim.height}
      containerWidth={containerWidth}
      containerHeight={containerHeight}
    />
  );
};

type ImageContentLoadedProps = {
  url: string;
  imageWidth: number;
  imageHeight: number;
  containerWidth: number;
  containerHeight: number;
};

const previewWidth = 300;
const previewHeight = 300;

const ImageContentLoaded = ({
  url,
  imageWidth,
  imageHeight,
  containerWidth,
  containerHeight,
}: ImageContentLoadedProps) => {
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
            overflow: 'hidden',
          }}>
          <img
            style={{
              maxWidth: '100%',
              maxHeight: '100%',
              objectFit: 'contain',
            }}
            src={url}
            alt="Custom"
            onClick={onClick}
          />
        </div>
        <div style={{color: '#666', textAlign: 'center', fontSize: '0.8em'}}>
          {imageWidth}x{imageHeight} - Click for more details
        </div>
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
        zoom={{maxZoomPixelRatio: 5}}
      />
    </>
  );
};
