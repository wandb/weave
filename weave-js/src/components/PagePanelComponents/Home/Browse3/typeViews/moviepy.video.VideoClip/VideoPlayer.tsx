import React, {FC, useEffect, useState} from 'react';
import Lightbox from 'yet-another-react-lightbox';
import Fullscreen from 'yet-another-react-lightbox/plugins/fullscreen';
import Video from 'yet-another-react-lightbox/plugins/video';
import {AutoSizer} from 'react-virtualized';

import {StyledTooltip, TooltipHint} from '../../../../../DraggablePopups';
import {LoadingDots} from '../../../../../LoadingDots';
import {NotApplicable} from '../../NotApplicable';
import {useWFHooks} from '../../pages/wfReactInterface/context';
import {CustomWeaveTypePayload} from '../customWeaveType.types';

type VideoClipTypePayload = CustomWeaveTypePayload<
  'moviepy.video.VideoClip.VideoClip',
  {'video.gif': string} | {'video.mp4': string} | {'video.webm': string}
>;

type VideoPlayerProps = {
  entity: string;
  project: string;
  data: VideoClipTypePayload;
};

export const VideoPlayer = (props: VideoPlayerProps) => (
  <AutoSizer style={{height: '100%', width: '100%'}}>
    {({width, height}) => {
      if (width === 0 || height === 0) {
        return null;
      }
      return (
        <VideoPlayerWithSize
          {...props}
          containerWidth={width}
          containerHeight={height}
        />
      );
    }}
  </AutoSizer>
);

type VideoPlayerWithSizeProps = VideoPlayerProps & {
  containerWidth: number;
  containerHeight: number;
};

const VideoPlayerWithSize = ({
  entity,
  project,
  data,
  containerWidth,
  containerHeight,
}: VideoPlayerWithSizeProps) => {
  const {useFileContent} = useWFHooks();
  const videoTypes = {
    'video.gif': 'gif',
    'video.mp4': 'mp4',
    'video.webm': 'webm',
  } as const;

  const videoKey = Object.keys(data.files).find(key => key in videoTypes) as
    | keyof VideoClipTypePayload['files']
    | undefined;
  const videoBinary = useFileContent(
    entity,
    project,
    videoKey ? data.files[videoKey] : '',
    {skip: !videoKey}
  );

  if (!videoKey) {
    return <NotApplicable />;
  } else if (videoBinary.loading) {
    return <LoadingDots />;
  } else if (videoBinary.result == null) {
    return <span></span>;
  }

  const fileExt = videoTypes[videoKey as keyof typeof videoTypes];

  return (
    <VideoPlayerWithData
      fileExt={fileExt}
      buffer={videoBinary.result}
      containerWidth={containerWidth}
      containerHeight={containerHeight}
    />
  );
};

type VideoPlayerWithDataProps = {
  fileExt: 'gif' | 'mp4' | 'webm';
  buffer: ArrayBuffer;
  containerWidth: number;
  containerHeight: number;
};

const VideoPlayerWithData = ({
  fileExt,
  buffer,
  containerWidth,
  containerHeight,
}: VideoPlayerWithDataProps) => {
  const [url, setUrl] = useState<string>('');

  useEffect(() => {
    let mimeType: string;
    switch (fileExt) {
      case 'gif':
        mimeType = 'image/gif';
        break;
      case 'mp4':
        mimeType = 'video/mp4';
        break;
      case 'webm':
        mimeType = 'video/webm';
        break;
      default:
        mimeType = 'video/mp4';
    }
    
    const blob = new Blob([buffer], {
      type: mimeType,
    });
    const objectUrl = URL.createObjectURL(blob);
    setUrl(objectUrl);

    return () => {
      URL.revokeObjectURL(objectUrl);
    };
  }, [buffer, fileExt]);

  if (!url) {
    return <LoadingDots />;
  }

  return (
    <VideoPlayerLoaded
      url={url}
      fileExt={fileExt}
      containerWidth={containerWidth}
      containerHeight={containerHeight}
    />
  );
};

type VideoPlayerLoadedProps = {
  url: string;
  fileExt: 'gif' | 'mp4' | 'webm';
  containerWidth: number;
  containerHeight: number;
};

const previewWidth = 300;
const previewHeight = 300;

const VideoPlayerLoaded = ({
  url,
  fileExt,
  containerWidth,
  containerHeight,
}: VideoPlayerLoadedProps) => {
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const onClick = () => setLightboxOpen(true);

  const isGif = fileExt === 'gif';
  
  // For GIFs, we use an img element
  // For MP4, we use video element with controls
  let videoElement;
  if (isGif) {
    videoElement = (
      <img
        style={{
          maxWidth: '100%',
          maxHeight: '100%',
          cursor: 'pointer',
        }}
        src={url}
        alt="Video clip (GIF)"
        onClick={onClick}
      />
    );
  } else {
    videoElement = (
      <video
        style={{
          maxWidth: '100%',
          maxHeight: '100%',
          cursor: 'pointer',
        }}
        src={url}
        controls
        controlsList="nodownload"
        onClick={onClick}
      />
    );
  }

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
          {isGif ? (
            <img
              style={{
                maxWidth: '100%',
                maxHeight: '100%',
                objectFit: 'contain',
              }}
              src={url}
              alt="Video clip (GIF)"
              onClick={onClick}
            />
          ) : (
            <video
              style={{
                maxWidth: '100%',
                maxHeight: '100%',
                objectFit: 'contain',
              }}
              src={url}
              controls
              controlsList="nodownload"
              onClick={onClick}
            />
          )}
        </div>
        <TooltipHint>
          {fileExt.toUpperCase()} Video - Click for more details
        </TooltipHint>
      </div>
    );
    videoElement = (
      <StyledTooltip enterDelay={500} title={preview}>
        {videoElement}
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
        {videoElement}
      </div>
      <Lightbox
        plugins={[Fullscreen, Video]}
        open={lightboxOpen}
        close={() => setLightboxOpen(false)}
        controller={{
          closeOnBackdropClick: true,
        }}
        slides={[
          isGif
            ? {src: url}
            : {
                type: 'video',
                sources: [{src: url, type: fileExt === 'webm' ? 'video/webm' : 'video/mp4'}],
              },
        ]}
        render={{
          // Hide previous and next buttons because we only have one video
          buttonPrev: () => null,
          buttonNext: () => null,
        }}
        carousel={{finite: true}}
      />
    </>
  );
};