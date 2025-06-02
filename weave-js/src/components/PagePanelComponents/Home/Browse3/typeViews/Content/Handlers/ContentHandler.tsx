import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import React, {useEffect} from 'react';

import {handlePDFMimetype} from './PDFHandler';
import {handleAudioMimetype} from './AudioHandler';
import {handleVideoMimetype} from './VideoHandler';
import {handleImageMimetype} from './ImageHandler';
import {handleGenericMimetype} from './GenericHandler';
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

type HandlerReturnType = {
  body: React.ReactNode;
  tooltipHint: string;
  tooltipPreview?: React.ReactNode;
};


export const handleMimetype = ({
  mimetype,
  ...handlerProps
}: HandlerProps): HandlerReturnType => {
  if (mimetype === 'application/pdf') {
    return handlePDFMimetype({mimetype, ...handlerProps});
  } else if (mimetype.startsWith('audio/')) {
    return handleAudioMimetype({mimetype, ...handlerProps});
  } else if (mimetype.startsWith('video/')) {
    return handleVideoMimetype({mimetype, ...handlerProps});
  } else if (mimetype.startsWith('image/')) {
    return handleImageMimetype({mimetype, ...handlerProps});
  } else {
    return handleGenericMimetype({mimetype, ...handlerProps});
  }
};
