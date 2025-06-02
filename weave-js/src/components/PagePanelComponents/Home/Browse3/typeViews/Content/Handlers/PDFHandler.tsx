import {Button} from '@wandb/weave/components/Button';
import React from 'react';

import {TailwindContents} from '@wandb/weave/components/Tailwind';
import {CustomLink} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/common/Links';
import {PDFView} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/typeViews/Content/Views';
import {HandlerProps, HandlerReturnType} from './Shared';

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

export const handlePDFMimetype = ({
  iconStart,
  filename,
  showPreview,
  contentResult,
  isDownloading,
  openPreview,
  closePreview,
  doSave,
}: HandlerProps): HandlerReturnType => {
  const iconAndText = (
    <CustomLink
      variant="secondary"
      icon={iconStart}
      onClick={openPreview}
      text={filename}
    />
  );
  const preview = showPreview && contentResult && (
    <PDFView
      open={true}
      onClose={closePreview}
      blob={contentResult}
      onDownload={doSave}
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
  };
};
