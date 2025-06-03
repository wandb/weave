import {Button} from '@wandb/weave/components/Button';
import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import React, {useEffect, useContext, useState, useRef} from 'react';
import {IconPlay} from '@wandb/weave/components/Icon';
import {TailwindContents} from '@wandb/weave/components/Tailwind';
import {CustomLink} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/common/Links';
import {VideoPopup, VideoThumbnail, VideoContent} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/typeViews/Content/Views';
import {HandlerProps, ContentTooltipWrapper, ContentMetadataTooltip} from './Shared';
import { WeaveflowPeekContext } from '../../../context';

type CreateToolTipPreviewProps = {
  contentResult: Blob | null;
  isDownloading: boolean;
  setIsDownloading: (downloading: boolean) => void;
  onClick: () => void;
  previewComponent: (contentResult: Blob) => React.ReactNode;
};

const CreateToolTipPreview = ({
  contentResult,
  isDownloading,
  setIsDownloading,
  previewComponent,
}: CreateToolTipPreviewProps) => {
  useEffect(() => {
    if (!isDownloading && !contentResult) {
      setIsDownloading(true);
    }
  });
  return (
    <>
      {contentResult && previewComponent(contentResult)}
      {!contentResult && <LoadingDots />}
    </>
  );
};

const DownloadButton = ({
  isDownloading,
  doSave,
}: {
  isDownloading: boolean;
  doSave: () => void;
}) => {
  return (
    <Button
      icon={isDownloading ? 'loading' : 'download'}
      variant="ghost"
      size="small"
      onClick={isDownloading ? undefined : doSave}
    />
  );
};

const VideoHandlerComponent = ({
  iconStart,
  filename,
  mimetype,
  size,
  showPreview,
  contentResult,
  setShowPreview,
  setIsDownloading,
  doSave,
  isDownloading,
  videoPlaybackState,
  updateVideoPlaybackState,
}: HandlerProps) => {
  const onTextClick = () => {
    setShowPreview(true);
    if (!contentResult) {
      setIsDownloading(true);
    }
  };

  const onClose = () => {
    setShowPreview(false);
  };

  const iconAndText = (
    <CustomLink
      variant="secondary"
      icon={iconStart}
      onClick={onTextClick}
      text={filename}
    />
  );

  const preview = showPreview && contentResult && (
    <VideoPopup
      src={contentResult}
      isOpen={true}
      onClose={onClose}
      initialTime={videoPlaybackState?.currentTime}
      initialVolume={videoPlaybackState?.volume}
      initialMuted={videoPlaybackState?.muted}
      onTimeUpdate={time => updateVideoPlaybackState?.({currentTime: time})}
      onVolumeChange={volume => updateVideoPlaybackState?.({volume})}
      onMuteChange={muted => updateVideoPlaybackState?.({muted})}
    />
  );

  if (showPreview) {
    return (
      <TailwindContents>
        {iconAndText}
        {preview}
      </TailwindContents>
    );
  }

  const previewComponent = (result: Blob) => {
    return <VideoThumbnail src={result} onClick={onTextClick} />;
  };

  const tooltipPreview = (
    <CreateToolTipPreview
      onClick={onTextClick}
      previewComponent={previewComponent}
      isDownloading={isDownloading}
      setIsDownloading={val => {
        setIsDownloading(val);
      }}
      contentResult={contentResult}
    />
  );

  const tooltipTrigger = (
    <ContentTooltipWrapper
      showPreview={false}
      tooltipHint="Click icon or filename to preview, button to download"
      tooltipPreview={tooltipPreview}
      body={iconAndText}
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

const VideoPreview = ({
  height,
  filename,
  mimetype,
  size,
  contentResult,
  isDownloading,
  setIsDownloading,
  videoPlaybackState,
  updateVideoPlaybackState,
}: HandlerProps) => {
  const [showVideoPopup, setShowVideoPopup] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    if (!isDownloading && !contentResult) {
      setIsDownloading(true);
    }
  }, [isDownloading, contentResult, setIsDownloading]);

  const handleClick = () => {
    if (height < 24) {
      setShowVideoPopup(true);
    }
  };

  const handleClosePopup = () => {
    setShowVideoPopup(false);
  };

  if (!contentResult) {
    return <LoadingDots />;
  }

  console.log(height)
  if (height < 24) {
    const thumbnailComponent = (
      <div
        style={{
          height: 38,
          width: 68,
          cursor: 'pointer',
          position: 'relative',
          overflow: 'hidden',
        }}
        onClick={handleClick}
      >
        <VideoContent src={contentResult} videoRef={videoRef} isThumbnail={true} />
        <div className="absolute inset-0 flex items-center justify-center bg-black/30 transition-all duration-200 hover:bg-black/20">
          <IconPlay className="text-white text-xs" />
        </div>
      </div>
    );

    return (
      <>
        <ContentTooltipWrapper
          showPreview={false}
          tooltipHint="Click to open video in popup"
          body={thumbnailComponent}
        >
          <ContentMetadataTooltip
            filename={filename}
            mimetype={mimetype}
            size={size}
          />
        </ContentTooltipWrapper>
        {showVideoPopup && (
          <VideoPopup
            src={contentResult}
            isOpen={true}
            onClose={handleClosePopup}
            initialTime={videoPlaybackState?.currentTime}
            initialVolume={videoPlaybackState?.volume}
            initialMuted={videoPlaybackState?.muted}
            onTimeUpdate={time => updateVideoPlaybackState?.({currentTime: time})}
            onVolumeChange={volume => updateVideoPlaybackState?.({volume})}
            onMuteChange={muted => updateVideoPlaybackState?.({muted})}
          />
        )}
      </>
    );
  }
  return (
    <VideoThumbnail src={contentResult} width="100%" height="100%"/>
  )
};

export const VideoHandler = (props: HandlerProps) => {
  const {isPeeking} = useContext(WeaveflowPeekContext);
  if (isPeeking) {
    return <VideoPreview {...props} />;
  }
  return <VideoHandlerComponent {...props} />;
};
