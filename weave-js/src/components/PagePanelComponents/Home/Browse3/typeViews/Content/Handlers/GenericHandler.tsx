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
  iconWithText,
  filename,
  mimetype,
  size,
  isDownloading,
  doSave,
  showPreview,
}: HandlerProps) => {
  // Always render iconWithText wrapped in appropriate container
  const content = (
    <ContentTooltipWrapper
      showPreview={showPreview}
      tooltipHint="Click button to download"
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
        {content}
        {!showPreview && (
          <div className="opacity-0 group-hover:opacity-100">
            <DownloadButton isDownloading={isDownloading} doSave={doSave} />
          </div>
        )}
      </div>
    </TailwindContents>
  );
};
