import {Button} from '@wandb/weave/components/Button';
import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import React, {useEffect} from 'react';

import {TailwindContents} from '@wandb/weave/components/Tailwind';
import {CustomLink} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/common/Links';
import {ImageThumbnail, ImageViewport} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/typeViews/Content/Views';
import {HandlerProps, ContentTooltipWrapper, ContentMetadataTooltip} from './Shared';


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

export const ImageHandler = ({
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
    <ImageViewport blob={contentResult} isOpen={true} onClose={onClose} />
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

  const previewComponent = (result: Blob) => {
    return <ImageThumbnail blob={result} onClick={onTextClick} />;
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

  return (
    <ContentTooltipWrapper
      showPreview={showPreview}
      tooltipHint="Click icon or filename to preview, button to download"
      tooltipPreview={tooltipPreview}
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
