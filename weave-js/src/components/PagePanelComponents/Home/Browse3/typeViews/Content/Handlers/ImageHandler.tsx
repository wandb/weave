import {Button} from '@wandb/weave/components/Button';
import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import React, {useEffect, useContext, useState, useMemo, useCallback} from 'react';

import {TailwindContents} from '@wandb/weave/components/Tailwind';
import {CustomLink} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/common/Links';
import {ImageThumbnail, ImageViewport} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/typeViews/Content/Views';
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

const ImageHandlerComponent = ({
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

  if (showPreview) {
    return (
      <TailwindContents>
        {iconAndText}
        {preview}
      </TailwindContents>
    );
  }

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

const ImagePreview = ({
  height,
  filename,
  mimetype,
  size,
  contentResult,
  isDownloading,
  setIsDownloading,
}: HandlerProps) => {
  const [showImagePopup, setShowImagePopup] = useState(false);

  useEffect(() => {
    if (!isDownloading && !contentResult) {
      setIsDownloading(true);
    }
  }, [isDownloading, contentResult, setIsDownloading]);

  const handleClick = useCallback(() => {
    setShowImagePopup(true);
  }, []);

  const handleClosePopup = useCallback(() => {
    setShowImagePopup(false);
  }, []);

  const memoizedSmallThumbnail = useMemo(() => (
    contentResult && <ImageThumbnail blob={contentResult} onClick={handleClick} height={38} width={68} />
  ), [contentResult, handleClick]);

  if (!contentResult) {
    return <LoadingDots />;
  }

  if (height < 24) {
    return (
      <>
        <ContentTooltipWrapper
          showPreview={false}
          tooltipHint="Click to open image in popup"
          body={memoizedSmallThumbnail}
        >
          <ContentMetadataTooltip
            filename={filename}
            mimetype={mimetype}
            size={size}
          />
        </ContentTooltipWrapper>
        <ImageViewport
          blob={contentResult}
          isOpen={showImagePopup}
          onClose={handleClosePopup}
        />
      </>
    );
  }
  const thumbnailComponent = <ImageThumbnail blob={contentResult} onClick={handleClick} width="100%" height="100%"/>
  return (
      <>
        <ContentTooltipWrapper
          showPreview={false}
          tooltipHint="Click to open image in popup"
          body={thumbnailComponent}

        >
          <ContentMetadataTooltip
            filename={filename}
            mimetype={mimetype}
            size={size}
          />
        </ContentTooltipWrapper>
        {showImagePopup && (
          <ImageViewport
            blob={contentResult}
            isOpen={true}
            onClose={handleClosePopup}
          />
        )}
      </>
  )
};

export const ImageHandler = (props: HandlerProps) => {
  const {isPeeking} = useContext(WeaveflowPeekContext);
  if (isPeeking) {
    return <ImagePreview {...props} />;
  }
  return <ImageHandlerComponent {...props} />;
};
