import {Button} from '@wandb/weave/components/Button';
import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import React, {useEffect, useContext} from 'react';

import {TailwindContents} from '@wandb/weave/components/Tailwind';
import {CustomLink} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/common/Links';
import {MiniAudioViewer} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/typeViews/Content/Views';
import {HandlerProps, ContentTooltipWrapper, ContentMetadataTooltip} from './Shared';
import { WeaveflowPeekContext } from '../../../context';

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

const AudioHandlerComponent = ({
  iconWithText,
  filename,
  mimetype,
  size,
  showPreview,
  contentResult,
  setShowPreview,
  setIsDownloading,
  doSave,
  isDownloading,
}: HandlerProps) => {
  const onTextClick = () => {
    setShowPreview(true);
    if (!contentResult) {
      setIsDownloading(true);
    }
  };

  // For non-preview mode, use iconWithText directly (it already handles clicks)
  const clickableIconAndText = !showPreview ? iconWithText : null;

  const content = (
    <>
      {!showPreview && clickableIconAndText}
      {showPreview && contentResult && (
        <MiniAudioViewer
          audioSrc={contentResult}
          autoplay={false}
          height={24}
          downloadFile={doSave}
        />
      )}
    </>
  );

  if (showPreview) {
    return <TailwindContents>{content}</TailwindContents>;
  }

  const tooltipTrigger = (
    <ContentTooltipWrapper
      showPreview={false}
      tooltipHint="Click icon or filename to preview, button to download"
      body={clickableIconAndText}
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

const AudioPreview = ({
  filename,
  mimetype,
  size,
  contentResult,
  isDownloading,
  setIsDownloading,
}: HandlerProps) => {
  useEffect(() => {
    if (!isDownloading && !contentResult) {
      setIsDownloading(true);
    }
  }, [isDownloading, contentResult, setIsDownloading]);

  if (!contentResult) {
    return <LoadingDots />;
  }

  // For peek mode, show the audio player directly without tooltip
  return (
    <MiniAudioViewer
      audioSrc={contentResult}
      height={24}
      autoplay={false}
    />
  );
};

export const AudioHandler = (props: HandlerProps) => {
  const {isPeeking} = useContext(WeaveflowPeekContext);
  if (isPeeking) {
    return <AudioPreview {...props} />;
  }
  return <AudioHandlerComponent {...props} />;
};
