import {Button} from '@wandb/weave/components/Button';
import React from 'react';

import {TailwindContents} from '@wandb/weave/components/Tailwind';
import {CustomLink} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/common/Links';
import {MiniAudioViewer} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/typeViews/Content/Views';
import {HandlerProps, ContentTooltipWrapper, ContentMetadataTooltip} from './Shared';

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

export const AudioHandler = ({
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
}: HandlerProps) => {
  const onTextClick = () => {
    setShowPreview(true);
    if (!contentResult) {
      setIsDownloading(true);
    }
  };

  const iconAndText = (
    <>
      {!showPreview && (
        <CustomLink
          variant="secondary"
          icon={iconStart}
          onClick={onTextClick}
          text={filename}
        />
      )}
      {showPreview && contentResult && (
        <MiniAudioViewer
          audioSrc={contentResult}
          autoplay={true}
          height={24}
          downloadFile={doSave}
        />
      )}
    </>
  );

  const body = (
    <TailwindContents>
      {showPreview && iconAndText}
      {!showPreview && (
        <div className="group flex items-center gap-4">
          {iconAndText}
          {!showPreview && (
            <div className="opacity-0 group-hover:opacity-100">
              <DownloadButton isDownloading={isDownloading} doSave={doSave} />
            </div>
          )}
        </div>
      )}
    </TailwindContents>
  );

  return (
    <ContentTooltipWrapper
      showPreview={showPreview}
      tooltipHint="Click icon or filename to preview, button to download"
      body={body}
    >
      <ContentMetadataTooltip
        filename={filename}
        mimetype={mimetype}
        size={size}
      />
    </ContentTooltipWrapper>
  );
};
