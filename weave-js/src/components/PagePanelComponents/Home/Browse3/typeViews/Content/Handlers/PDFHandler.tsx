import {Button} from '@wandb/weave/components/Button';
import React from 'react';

import {TailwindContents} from '@wandb/weave/components/Tailwind';
import {CustomLink} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/common/Links';
import {PDFView} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/typeViews/Content/Views';
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

export const PDFHandler = ({
  iconWithText,
  filename,
  mimetype,
  size,
  showPreview,
  contentResult,
  isDownloading,
  openPreview,
  closePreview,
  doSave,
}: HandlerProps) => {
  // Use iconWithText directly (it already handles clicks)
  const clickableIconAndText = iconWithText;
  const preview = showPreview && contentResult && (
    <PDFView
      open={true}
      onClose={closePreview}
      blob={contentResult}
      onDownload={doSave}
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
