import React, {FC, useEffect, useState, useRef} from 'react';
import Lightbox from 'yet-another-react-lightbox';
import Fullscreen from 'yet-another-react-lightbox/plugins/fullscreen';
import Video from 'yet-another-react-lightbox/plugins/video';
import {AutoSizer} from 'react-virtualized';
import styled from 'styled-components';

import {StyledTooltip, TooltipHint} from '../../../../../DraggablePopups';
import {LoadingDots} from '../../../../../LoadingDots';
import {useContext} from 'react';
import {NotApplicable} from '../../NotApplicable';
import {useWFHooks} from '../../pages/wfReactInterface/context';
import {CustomWeaveTypePayload} from '../customWeaveType.types';
import { PILImageImageTypePayload, imageTypes } from '../PIL.Image.Image/PILImageImage';

type VideoClipTypePayload = CustomWeaveTypePayload<
  'moviepy.video.VideoClip.VideoClip',
  {'video.gif': string} | {'video.mp4': string} | {'video.webm': string}
>;

type VideoPlayerProps = {
  entity: string;
  project: string;
  mode?: string;
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
      title={data.custom_name || entity.split('-')[0]} // Using first part of entity as title if no custom name
    />
  );
};

type VideoPlayerWithDataProps = {
  fileExt: 'gif' | 'mp4' | 'webm';
  buffer: ArrayBuffer;
  previewImageUrl?: string;
  containerWidth: number;
  containerHeight: number;
  title: string;
};

const VideoPlayerWithData = ({
  fileExt,
  buffer,
  previewImageUrl,
  containerWidth,
  containerHeight,
  title,
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
      previewImageUrl={previewImageUrl}
      containerWidth={containerWidth}
      containerHeight={containerHeight}
      title={title}
    />
  );
};

type VideoPlayerLoadedProps = {
  url: string;
  fileExt: 'gif' | 'mp4' | 'webm';
  previewImageUrl?: string;
  containerWidth: number;
  containerHeight: number;
  title: string;
};

const previewWidth = 300;
const previewHeight = 300;

// Styled components for the custom video player
const VideoContainer = styled.div`
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  border-radius: 12px;
  overflow: hidden;
  background-color: white;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
`;

const VideoTitle = styled.div`
  font-size: 18px;
  font-weight: 500;
  padding: 16px;
  text-align: center;
  color: #333;
`;

const VideoLinkText = styled.div`
  font-size: 18px;
  font-weight: 500;
  padding: 16px;
  text-align: center;
  color: #333;
`;
const VideoWrapper = styled.div`
  position: relative;
  flex: 1;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
`;

const VideoElement = styled.video`
  width: 100%;
  height: 100%;
  object-fit: contain;
`;

const PreviewImageContainer = styled.div`
  position: absolute;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  z-index: 2;
`;

const PreviewImage = styled.img`
  width: 100%;
  height: 100%;
  object-fit: contain;
`;

const PlayButtonOverlay = styled.div`
  position: absolute;
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.2s ease, background-color 0.2s ease;

  &:hover {
    transform: scale(1.1);
    background-color: rgba(0, 0, 0, 0.7);
  }

  svg {
    width: 40px;
    height: 40px;
    fill: white;
  }
`;

const CustomControls = styled.div`
  display: flex;
  align-items: center;
  padding: 12px 16px;
  background-color: white;
  border-top: 1px solid #eee;
`;

const PlayButton = styled.button`
  background: none;
  border: none;
  cursor: pointer;
  color: #666;
  font-size: 24px;
  padding: 0;
  margin-right: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  
  &:hover {
    color: #333;
  }
  
  &:focus {
    outline: none;
  }
`;

const ResetButton = styled(PlayButton)`
  transform: scaleX(-1);
`;

const RewindButton = styled(PlayButton)``;

const TimeDisplay = styled.div`
  color: #666;
  font-size: 14px;
  margin: 0 12px;
  font-variant-numeric: tabular-nums;
`;

const ProgressContainer = styled.div`
  flex: 1;
  margin: 0 12px;
  position: relative;
  height: 6px;
  background-color: #e0e0e0;
  border-radius: 3px;
  cursor: pointer;
`;

const ProgressBar = styled.div<{progress: number}>`
  position: absolute;
  height: 100%;
  width: ${props => props.progress * 100}%;
  background-color: #4a9eff;
  border-radius: 3px;
`;

const ProgressHandle = styled.div<{progress: number}>`
  position: absolute;
  left: ${props => props.progress * 100}%;
  top: 50%;
  transform: translate(-50%, -50%);
  width: 16px;
  height: 16px;
  background-color: #4a9eff;
  border-radius: 50%;
  border: 2px solid white;
  box-shadow: 0 1px 2px rgba(0,0,0,0.2);
`;

const PlaybackSpeedButton = styled.button`
  background: none;
  border: none;
  cursor: pointer;
  color: #666;
  font-size: 14px;
  font-weight: 500;
  padding: 4px 8px;
  margin-left: 12px;
  border-radius: 4px;

  &:hover {
    background-color: #f5f5f5;
  }

  &:focus {
    outline: none;
  }
`;

const FullscreenButton = styled(PlayButton)`
  margin-left: 8px;
`;

const formatTime = (seconds: number): string => {
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.floor(seconds % 60);
  return `${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`;
};

import VideoViewer from '../../../../../../components/Panel2/VideoViewer'
const VideoPlayerLoaded = ({
  url,
  fileExt,
  previewImageUrl,
  containerWidth,
  containerHeight,
  title,
}: VideoPlayerLoadedProps) => {
  if (containerHeight >= 1) {
    return (
      <VideoViewer videoSrc={url} width={containerWidth} height={containerHeight}/>
    )
  } else return null
};
