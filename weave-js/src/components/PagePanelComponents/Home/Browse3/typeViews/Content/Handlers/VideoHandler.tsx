import {Button} from '@wandb/weave/components/Button';
import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import React, {useEffect} from 'react';

import {TailwindContents} from '@wandb/weave/components/Tailwind';
import {CustomLink} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/common/Links';
import {VideoPopup, VideoThumbnail} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/typeViews/Content/Views';
import {HandlerProps, HandlerReturnType} from './Shared';

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

export const handleVideoMimetype = ({
  iconStart,
  filename,
  showPreview,
  contentResult,
  setShowPreview,
  setIsDownloading,
  doSave,
  isDownloading,
  videoPlaybackState,
  updateVideoPlaybackState,
}: HandlerProps): HandlerReturnType => {
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

  const body = (
    <TailwindContents>
      <div className="group flex items-center gap-4">
        {iconAndText}
        {preview}
        <div className="opacity-0 group-hover:opacity-100">
          <DownloadButton isDownloading={isDownloading} doSave={doSave} />
        </div>
      </div>
    </TailwindContents>
  );

  return {
    body,
    tooltipHint: 'Click icon or filename to preview, button to download',
    tooltipPreview,
  };
};
