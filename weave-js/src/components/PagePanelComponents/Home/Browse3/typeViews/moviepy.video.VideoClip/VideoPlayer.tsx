import React, {FC, useEffect, useState, useRef} from 'react';
import Lightbox from 'yet-another-react-lightbox';
import Fullscreen from 'yet-another-react-lightbox/plugins/fullscreen';
import Video from 'yet-another-react-lightbox/plugins/video';
import {AutoSizer} from 'react-virtualized';
import styled from 'styled-components';

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
      title={data.custom_name || entity.split('-')[0]} // Using first part of entity as title if no custom name
    />
  );
};

type VideoPlayerWithDataProps = {
  fileExt: 'gif' | 'mp4' | 'webm';
  buffer: ArrayBuffer;
  containerWidth: number;
  containerHeight: number;
  title: string;
};

const VideoPlayerWithData = ({
  fileExt,
  buffer,
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
      containerWidth={containerWidth}
      containerHeight={containerHeight}
      title={title}
    />
  );
};

type VideoPlayerLoadedProps = {
  url: string;
  fileExt: 'gif' | 'mp4' | 'webm';
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

const VideoPlayerLoaded = ({
  url,
  fileExt,
  containerWidth,
  containerHeight,
  title,
}: VideoPlayerLoadedProps) => {
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const progressRef = useRef<HTMLDivElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [playbackRate, setPlaybackRate] = useState(1);

  const isGif = fileExt === 'gif';
  
  useEffect(() => {
    const videoElement = videoRef.current;
    if (!videoElement || isGif) return;

    const updateTime = () => {
      setCurrentTime(videoElement.currentTime);
      setDuration(videoElement.duration);
    };

    const handlePlay = () => setIsPlaying(true);
    const handlePause = () => setIsPlaying(false);
    const handleEnded = () => setIsPlaying(false);

    videoElement.addEventListener('timeupdate', updateTime);
    videoElement.addEventListener('durationchange', updateTime);
    videoElement.addEventListener('play', handlePlay);
    videoElement.addEventListener('pause', handlePause);
    videoElement.addEventListener('ended', handleEnded);

    return () => {
      videoElement.removeEventListener('timeupdate', updateTime);
      videoElement.removeEventListener('durationchange', updateTime);
      videoElement.removeEventListener('play', handlePlay);
      videoElement.removeEventListener('pause', handlePause);
      videoElement.removeEventListener('ended', handleEnded);
    };
  }, [isGif]);

  const togglePlay = () => {
    const videoElement = videoRef.current;
    if (!videoElement) return;

    if (isPlaying) {
      videoElement.pause();
    } else {
      videoElement.play();
    }
  };

  const handleRewind = () => {
    const videoElement = videoRef.current;
    if (!videoElement) return;
    
    videoElement.currentTime = Math.max(0, videoElement.currentTime - 10);
  };
  
  const handleReset = () => {
    const videoElement = videoRef.current;
    if (!videoElement) return;
    
    videoElement.currentTime = 0;
  };

  const handleProgressClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const progressElement = progressRef.current;
    const videoElement = videoRef.current;
    if (!progressElement || !videoElement) return;

    const rect = progressElement.getBoundingClientRect();
    const clickPosition = (e.clientX - rect.left) / rect.width;
    videoElement.currentTime = clickPosition * videoElement.duration;
  };

  const toggleFullscreen = () => {
    setLightboxOpen(true);
  };

  const togglePlaybackRate = () => {
    const rates = [0.5, 1, 1.5, 2];
    const currentIndex = rates.indexOf(playbackRate);
    const nextIndex = (currentIndex + 1) % rates.length;
    
    const videoElement = videoRef.current;
    if (videoElement) {
      const newRate = rates[nextIndex];
      videoElement.playbackRate = newRate;
      setPlaybackRate(newRate);
    }
  };

  // For GIFs, we use an img element
  if (isGif) {
    return (
      <VideoContainer>
        <VideoTitle>{title}</VideoTitle>
        <VideoWrapper>
          <img
            style={{
              maxWidth: '100%',
              maxHeight: '100%',
              objectFit: 'contain',
            }}
            src={url}
            alt="Video clip (GIF)"
            onClick={() => setLightboxOpen(true)}
          />
        </VideoWrapper>
        <Lightbox
          plugins={[Fullscreen]}
          open={lightboxOpen}
          close={() => setLightboxOpen(false)}
          controller={{
            closeOnBackdropClick: true,
          }}
          slides={[{src: url}]}
          render={{
            buttonPrev: () => null,
            buttonNext: () => null,
          }}
          carousel={{finite: true}}
        />
      </VideoContainer>
    );
  }

  const progress = duration > 0 ? currentTime / duration : 0;

  return (
    <>
      <VideoContainer>
        <VideoTitle>{title}</VideoTitle>
        <VideoWrapper>
          <VideoElement
            ref={videoRef}
            src={url}
            onClick={togglePlay}
            playsInline
          />
        </VideoWrapper>
        <CustomControls>
          <PlayButton onClick={togglePlay}>
            {isPlaying ? (
              <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                <rect x="6" y="4" width="4" height="16" rx="1" />
                <rect x="14" y="4" width="4" height="16" rx="1" />
              </svg>
            ) : (
              <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                <path d="M8 5.14v14l11-7-11-7z" />
              </svg>
            )}
          </PlayButton>
          <ResetButton onClick={handleReset}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 5V1L7 6l5 5V7c3.31 0 6 2.69 6 6s-2.69 6-6 6-6-2.69-6-6H4c0 4.42 3.58 8 8 8s8-3.58 8-8-3.58-8-8-8z" />
            </svg>
          </ResetButton>
          <RewindButton onClick={handleRewind}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
              <path d="M7 6c.55 0 1 .45 1 1v10c0 .55-.45 1-1 1s-1-.45-1-1V7c0-.55.45-1 1-1zm3.66 6.82l5.77 4.07c.66.47 1.58-.01 1.58-.82V7.93c0-.81-.91-1.28-1.58-.82l-5.77 4.07c-.57.4-.57 1.24 0 1.64z" />
            </svg>
          </RewindButton>
          <TimeDisplay>
            {formatTime(currentTime)} / {formatTime(duration)}
          </TimeDisplay>
          <ProgressContainer ref={progressRef} onClick={handleProgressClick}>
            <ProgressBar progress={progress} />
            <ProgressHandle progress={progress} />
          </ProgressContainer>
          <PlaybackSpeedButton onClick={togglePlaybackRate}>
            {playbackRate}x
          </PlaybackSpeedButton>
          <FullscreenButton onClick={toggleFullscreen}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
              <path d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z" />
            </svg>
          </FullscreenButton>
        </CustomControls>
      </VideoContainer>
      <Lightbox
        plugins={[Fullscreen, Video]}
        open={lightboxOpen}
        close={() => setLightboxOpen(false)}
        controller={{
          closeOnBackdropClick: true,
        }}
        slides={[
          {
            type: 'video',
            sources: [{src: url, type: fileExt === 'webm' ? 'video/webm' : 'video/mp4'}],
          },
        ]}
        render={{
          buttonPrev: () => null,
          buttonNext: () => null,
        }}
        carousel={{finite: true}}
      />
    </>
  );
};