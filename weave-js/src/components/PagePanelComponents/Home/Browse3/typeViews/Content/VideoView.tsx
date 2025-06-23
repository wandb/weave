import {Button} from '@wandb/weave/components/Button';
import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import React, {useEffect, useContext, useState, useRef, useCallback} from 'react';
import {IconPlay} from '@wandb/weave/components/Icon';
import {TailwindContents} from '@wandb/weave/components/Tailwind';
import {ContentTooltipWrapper, ContentMetadataTooltip, DownloadButton, getIconName, IconWithText} from './Shared';
import * as Dialog from '@wandb/weave/components/Dialog/Dialog';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import {ContentViewMetadataLoadedProps} from './types';
import {useWFHooks} from '../../pages/wfReactInterface/context';

type VideoProps = {
  src: Blob | string;
};
type VideoContentInnerProps = {
  isThumbnail: boolean;
  videoRef: React.RefObject<HTMLVideoElement>;
  autoplay?: boolean;
  initialTime?: number;
  initialMuted?: boolean;
  initialVolume?: number;
  onTimeUpdate?: (time: number) => void;
  onMuteChange?: (muted: boolean) => void;
  onVolumeChange?: (volume: number) => void;
} & VideoProps;

type VideoPreviewProps = {
  onClick?: () => void;
  height?: number | string;
  width?: number | string;
} & VideoProps;

type VideoPopupProps = {
  isOpen: boolean;
  onClose: () => void;
  initialTime?: number;
  initialMuted?: boolean;
  initialVolume?: number;
  onTimeUpdate?: (time: number) => void;
  onMuteChange?: (muted: boolean) => void;
  onVolumeChange?: (volume: number) => void;
} & VideoProps;

// Save a Blob as a content in the user's downloads folder in a
// cross-browser compatible way.
const saveBlob = (blob: Blob, filename: string) => {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  });
};

const VideoContentInner: React.FC<VideoContentInnerProps> = ({
  src,
  isThumbnail,
  videoRef,
  autoplay,
  initialTime,
  initialMuted,
  initialVolume,
  onTimeUpdate,
  onMuteChange,
  onVolumeChange,
}) => {
  const [url, setUrl] = useState<string>('');

  useEffect(() => {
    if (src instanceof Blob) {
      const objectUrl = URL.createObjectURL(src);
      setUrl(objectUrl);
      return () => URL.revokeObjectURL(objectUrl);
    } else {
      setUrl(src);
      return;
    }
  }, [src]);

  useEffect(() => {
    const videoElement = videoRef.current;
    if (videoElement && url) {
      const handleTimeUpdate = () => {
        if (onTimeUpdate) {
          onTimeUpdate(videoElement.currentTime);
        }
      };
      const handleVolumeChange = () => {
        if (onVolumeChange) {
          onVolumeChange(videoElement.volume);
        }
        if (onMuteChange) {
          onMuteChange(videoElement.muted);
        }
      };

      videoElement.addEventListener('timeupdate', handleTimeUpdate);
      videoElement.addEventListener('volumechange', handleVolumeChange);

      if (!isThumbnail) {
        if (initialVolume !== undefined) {
          videoElement.volume = initialVolume;
        }
        if (initialMuted !== undefined) {
          videoElement.muted = initialMuted;
        } else {
          videoElement.muted = true; // Default to muted
        }
      }

      return () => {
        videoElement.removeEventListener('timeupdate', handleTimeUpdate);
        videoElement.removeEventListener('volumechange', handleVolumeChange);
      };
    }
    return;
  }, [
    videoRef,
    url,
    onTimeUpdate,
    onVolumeChange,
    onMuteChange,
    isThumbnail,
    initialVolume,
    initialMuted,
  ]);

  if (!url) {
    return <LoadingDots />;
  }

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        overflow: 'hidden',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}>
      <video
        ref={videoRef}
        src={url}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'contain',
        }}
        controls={!isThumbnail}
        autoPlay={autoplay ?? false}
        muted={isThumbnail ? true : initialMuted ?? true}
        loop={isThumbnail}
        onLoadedData={() => {
          if (videoRef.current) {
            if (isThumbnail) {
              const seekTime = Math.min(1, videoRef.current.duration * 0.25);
              videoRef.current.currentTime = seekTime;
            } else {
              if (initialTime) {
                videoRef.current.currentTime = initialTime;
              }
            }
          }
        }}
      />
    </div>
  );
};

export const VideoPopup: React.FC<VideoPopupProps> = ({
  src,
  isOpen,
  onClose,
  initialTime,
  initialMuted,
  initialVolume,
  onTimeUpdate,
  onMuteChange,
  onVolumeChange,
}) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  return (
    <Dialog.Root open={isOpen} onOpenChange={onClose}>
      <Dialog.Portal>
        <Dialog.Overlay />
        <Dialog.Content className="h-[60vh] w-[60vw] p-0">
          <VideoContentInner
            src={src}
            videoRef={videoRef}
            isThumbnail={false}
            autoplay={false}
            initialTime={initialTime}
            initialMuted={initialMuted}
            initialVolume={initialVolume}
            onTimeUpdate={onTimeUpdate}
            onMuteChange={onMuteChange}
            onVolumeChange={onVolumeChange}
          />
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
};

export const VideoPlayerThumbnail: React.FC<VideoPreviewProps> = ({src}) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isThumbnail, setIsThumbnail] = useState(true)
  return (
    <Tailwind>
      <div
        className="relative flex h-full w-full items-center justify-start"
        style={{cursor: 'pointer'}}
        onClick={() => setIsThumbnail(false)}>
        <div className="relative">
          <VideoContentInner src={src} videoRef={videoRef} isThumbnail={isThumbnail} />
          {isThumbnail && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/30 transition-all duration-200 hover:bg-black/20">
              <IconPlay className="text-white" />
            </div>
          )}
        </div>
      </div>
    </Tailwind>
  );
}

export const VideoThumbnail: React.FC<VideoPreviewProps> = ({src, width, height, onClick}) => {
  const thumbnailHeight = height ?? 38 * 3; // Default height of the cell row
  const thumbnailWidth = width ?? 68 * 3; // 16:9-ish ratio
  const [isThumbnail, setIsThumbnail] = useState(true);

  const videoPlayer = (
    <>
    {isThumbnail && (
      <div>
        <VideoContentInner src={src} videoRef={useRef<HTMLVideoElement>(null)} isThumbnail={isThumbnail} />
        <div className="absolute inset-0 flex items-center justify-center bg-black/30 transition-all duration-200 hover:bg-black/20">
          <IconPlay className="text-white" />
        </div>
      </div>
    )}
    {!isThumbnail && (<VideoContentInner src={src} videoRef={useRef<HTMLVideoElement>(null)} isThumbnail={isThumbnail} autoplay={true}/>)}
    </>
  )
  return (
    <Tailwind>
      <div
        className="relative flex h-full w-full items-center justify-start"
        style={{cursor: 'pointer'}}
        onClick={onClick ?? (() => setIsThumbnail(false))}>
        <div
          style={{height: thumbnailHeight, width: thumbnailWidth}}
          className="relative">
          {videoPlayer}
        </div>
      </div>
    </Tailwind>
  );
};

export const VideoContent = (props: ContentViewMetadataLoadedProps) => {
  const [contentResult, setContentResult] = useState<Blob | null>(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [videoPlaybackState, setVideoPlaybackState] = useState<{
    currentTime: number;
    volume: number;
    muted: boolean;
  }>({currentTime: 0, volume: 1, muted: true});
  const {useFileContent} = useWFHooks();
  const {metadata, project, entity, content} = props;
  const {filename, size, mimetype} = metadata;

  const contentContent = useFileContent({
    entity,
    project,
    digest: content,
    skip: !isDownloading,
  });

  // Store the last non-null content content result in state
  // We do this because passing skip: true to useFileContent will
  // result in contentContent.result getting returned as null even
  // if it was previously downloaded successfully.
  useEffect(() => {
    if (contentContent.result) {
      const blob = new Blob([contentContent.result], {
        type: mimetype,
      });

      setContentResult(blob);
      setIsDownloading(false);
    }
  }, [contentContent.result, mimetype]);

  const doSave = useCallback(() => {
    if (!contentResult) {
      console.error('No content result');
      return;
    }
    saveBlob(contentResult, filename);
  }, [contentResult, filename]);

  const downloadContent = () => {
    if (!contentResult && !isDownloading) {
      setIsDownloading(true);
    } else if (contentResult) {
      // We really want to know if we are duplicating these large downloads
      console.warn('Attempted to download previously loaded content.');
    }
  };

  const openPreview = () => {
    setShowPreview(true);
    if (!contentResult && !isDownloading) {
      downloadContent();
    }
  };

  const closePreview = () => {
    setShowPreview(false);
  };

  const updateVideoPlaybackState = useCallback(
    (newState: Partial<{currentTime: number; volume: number; muted: boolean}>) => {
      setVideoPlaybackState(prev => ({...prev, ...newState}));
    },
    []
  );

  const iconName = getIconName(mimetype);

  const iconWithText = (
    <div>
      <IconWithText
        iconName={iconName}
        filename={filename}
        onClick={openPreview}
      />
    </div>
  );

  const preview = showPreview && contentResult && (
    <VideoPopup
      src={contentResult}
      isOpen={true}
      onClose={closePreview}
      initialTime={videoPlaybackState.currentTime}
      initialVolume={videoPlaybackState.volume}
      initialMuted={videoPlaybackState.muted}
      onTimeUpdate={time => updateVideoPlaybackState({currentTime: time})}
      onVolumeChange={volume => updateVideoPlaybackState({volume})}
      onMuteChange={muted => updateVideoPlaybackState({muted})}
    />
  );

  if (showPreview) {
    return (
      <TailwindContents>
        {iconWithText}
        {preview}
      </TailwindContents>
    );
  }

  const CreateToolTipPreview = () => {
    useEffect(() => {
      if (!isDownloading && !contentResult) {
        setIsDownloading(true);
      }
    });
    return (
      <>
        {contentResult && <VideoThumbnail src={contentResult} onClick={openPreview} />}
        {!contentResult && <LoadingDots />}
      </>
    );
  };

  const tooltipPreview = <CreateToolTipPreview />;

  const tooltipTrigger = (
    <ContentTooltipWrapper
      showPreview={false}
      tooltipHint="Click icon or filename to preview, button to download"
      tooltipPreview={tooltipPreview}
      body={iconWithText}
    >
      <ContentMetadataTooltip
        filename={filename}
        mimetype={mimetype}
        size={size}
      />
    </ContentTooltipWrapper>
  );

  return (
    <TailwindContents>
      <div className="group flex items-center gap-4">
        {tooltipTrigger}
        <div className="opacity-0 group-hover:opacity-100">
          <DownloadButton isDownloading={isDownloading} doSave={doSave} />
        </div>
      </div>
    </TailwindContents>
  );
};
