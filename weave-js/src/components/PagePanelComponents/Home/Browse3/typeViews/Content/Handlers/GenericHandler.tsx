import {Button} from '@wandb/weave/components/Button';
import React from 'react';

import {TailwindContents} from '@wandb/weave/components/Tailwind';
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

export const GenericHandler = ({
  iconStart,
  filename,
  mimetype,
  size,
  isDownloading,
  doSave,
  showPreview,
}: HandlerProps) => {
  const iconAndText = (
    <>
      {iconStart}
      <span>{filename}</span>
    </>
  );

  const body = (
    <TailwindContents>
      <div className="group flex items-center gap-4">
        {iconAndText}
        <div className="opacity-0 group-hover:opacity-100">
          <DownloadButton isDownloading={isDownloading} doSave={doSave} />
        </div>
      </div>
    </TailwindContents>
  );

  return (
    <ContentTooltipWrapper
      showPreview={showPreview}
      tooltipHint="Click button to download"
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
