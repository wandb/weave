import {Button} from '@wandb/weave/components/Button';
import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import React, {useEffect, useContext, useState, useMemo, useCallback} from 'react';

import {TailwindContents} from '@wandb/weave/components/Tailwind';
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

  const onClose = () => {
    setShowPreview(false);
  };

  // Use iconWithText directly (it already handles clicks)
  const clickableIconAndText = iconWithText;

  const preview = showPreview && contentResult && (
    <ImageViewport blob={contentResult} isOpen={true} onClose={onClose} />
  );

  if (showPreview) {
    return (
      <TailwindContents>
        {iconWithText}
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

  const imageUrl = useMemo(() => {
    return contentResult ? URL.createObjectURL(contentResult) : '';
  }, [contentResult]);

  useEffect(() => {
    return () => {
      if (imageUrl) {
        URL.revokeObjectURL(imageUrl);
      }
    };
  }, [imageUrl]);

  const memoizedSmallThumbnail = useMemo(() => {
    if (!contentResult || !imageUrl) return null;
    return (
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
        <img
          style={{
            width: '100%',
            height: '100%',
            objectFit: 'contain',
          }}
          src={imageUrl}
          alt="Preview Thumbnail"
        />
        <div className="absolute inset-0 flex items-center justify-center bg-black/30 transition-all duration-200 hover:bg-black/20">
          <span className="text-xs text-white">🔍</span>
        </div>
      </div>
    );
  }, [contentResult, imageUrl, handleClick]);

  if (!contentResult) {
    return <LoadingDots />;
  }

  if (height < 21) {
    return (
      <>
        <ContentTooltipWrapper
          showPreview={false}
          tooltipHint="Click to open image in popup"
          body={memoizedSmallThumbnail}
          noTriggerWrap={true}
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
          noTriggerWrap={true}
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
