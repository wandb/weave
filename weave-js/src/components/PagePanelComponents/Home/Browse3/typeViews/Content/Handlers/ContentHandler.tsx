import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import React, {useEffect} from 'react';

import {PDFHandler} from './PDFHandler';
import {AudioHandler} from './AudioHandler';
import {VideoHandler} from './VideoHandler';
import {ImageHandler} from './ImageHandler';
import {GenericHandler} from './GenericHandler';
import {HandlerProps} from './Shared';

type CreateToolTipPreviewProps = {
  contentResult: Blob | null;
  isDownloading: boolean;
  setIsDownloading: (downloading: boolean) => void;
  onClick: () => void;
  previewComponent: (contentResult: Blob) => React.ReactNode;
};

export const CreateToolTipPreview = ({
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

export const getContentHandler = ({
  mimetype,
  ...handlerProps
}: HandlerProps) => {
  if (mimetype === 'application/pdf') {
    return <PDFHandler mimetype={mimetype} {...handlerProps} />;
  } else if (mimetype.startsWith('audio/')) {
    return <AudioHandler mimetype={mimetype} {...handlerProps} />;
  } else if (mimetype.startsWith('video/')) {
    return <VideoHandler mimetype={mimetype} {...handlerProps} />;
  } else if (mimetype.startsWith('image/')) {
    return <ImageHandler mimetype={mimetype} {...handlerProps} />;
  } else {
    return <GenericHandler mimetype={mimetype} {...handlerProps} />;
  }
};
