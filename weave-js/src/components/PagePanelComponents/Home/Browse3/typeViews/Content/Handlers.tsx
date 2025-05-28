import {Button} from '@wandb/weave/components/Button';
import React, {RefObject, useEffect, useRef} from 'react';
import {IconName, IconNames} from '../../../../../Icon';
import {CustomLink} from '../../pages/common/Links';
import {PDFView} from './PDFView';
import {VideoPopup, VideoThumbnail} from './VideoView';
import {MiniAudioViewer} from './AudioView';
import {ImageThumbnail, ImageViewport} from './ImageView';
import {TailwindContents} from '../../../../../Tailwind';
import { LoadingDots } from '@wandb/weave/components/LoadingDots';

const ICON_MAP: Record<string, IconName> = {
  'application/json': IconNames.JobProgramCode,
  'text/csv': IconNames.Table,
  'text/html': IconNames.JobProgramCode,
  'text/xml': IconNames.JobProgramCode,
};

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
  previewComponent
}: CreateToolTipPreviewProps) => {
  useEffect(() => {
    if(!isDownloading && !contentResult) {
      setIsDownloading(true)
    }
  })
  return (
    <>
      {contentResult && (
        previewComponent(contentResult)
      )}
      {!contentResult && (
        <LoadingDots />
      )}
    </>
  )
}
export const getIconName = (mimetype: string): IconName => {
  const iconName = ICON_MAP[mimetype];
  if (iconName) {
    return iconName;
  }

  const [type] = mimetype.split('/', 2);
  if (type === 'image') {
    return IconNames.Photo;
  } else if (type === 'audio') {
    return IconNames.MusicAudio;
  } else if (type === 'video') {
    return IconNames.VideoPlay;
  } else if (type === 'text') {
    return IconNames.Document;
  }

  return IconNames.Document;
};

type HandlerProps = {
  mimetype: string;
  filename: string;
  size: number;
  iconStart: React.ReactNode;
  showPreview: boolean;
  isDownloading: boolean;
  contentResult: Blob | null;
  openPreview: () => void;
  closePreview: () => void;
  doSave: () => void;
  setShowPreview: (show: boolean) => void;
  setIsDownloading: (downloading: boolean) => void;
};

type HandlerReturnType = {
  body: React.ReactNode;
  tooltipHint: string;
  tooltipPreview?: React.ReactNode;
}

const DownloadButton = ({
  isDownloading,
  doSave
}: { isDownloading: boolean, doSave: () => void}) =>{
  return (
    <Button
      icon={isDownloading ? 'loading' : 'download'}
      variant="ghost"
      size="small"
      onClick={isDownloading ? undefined : doSave}
    />
  )
}

const handlePDFMimetype = ({
  iconStart,
  filename,
  showPreview,
  contentResult,
  isDownloading,
  openPreview,
  closePreview,
  doSave,
}: HandlerProps) => {
  const iconAndText = (
    <CustomLink
      variant="secondary"
      icon={iconStart}
      onClick={openPreview}
      text={filename}
    />
  )
  const preview = (
    showPreview && contentResult && (
      <PDFView
        open={true}
        onClose={closePreview}
        blob={contentResult}
        onDownload={doSave}
      />
    )
  )
  const body = (
    <TailwindContents>
      <div className="flex items-center gap-4 group">
        {iconAndText}
        {preview}
        <div className="opacity-0 group-hover:opacity-100">
          <DownloadButton isDownloading={isDownloading} doSave={doSave} />
        </div>
      </div>
    </TailwindContents>
  )
  return {
    body,
    tooltipHint: 'Click icon or filename to preview, button to download',
  };
};

export const handleAudioMimetype = ({
  iconStart,
  filename,
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
        <div className="flex items-center gap-4 group">
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

  return {
    body,
    tooltipHint: 'Click icon or filename to preview, button to download',
  };
};

export const handleVideoMimetype = ({
  iconStart,
  filename,
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

  const preview = (
    showPreview && contentResult && (
      <VideoPopup
        src={contentResult}
        isOpen={true}
        onClose={onClose}
      />
    )
  );
  const previewComponent = (result: Blob) => {
    return <VideoThumbnail src={result} onClick={onTextClick}/>
  }

  const tooltipPreview = (
    <CreateToolTipPreview
      onClick={onTextClick}
      previewComponent={previewComponent}
      isDownloading={isDownloading}
      setIsDownloading={(val) => {setIsDownloading(val)}}
      contentResult={contentResult}
    />
  )

  const body = (
    <TailwindContents>
      <div className="flex items-center gap-4 group">
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
    tooltipPreview
  };
};

export const handleImageMimetype = ({
  iconStart,
  filename,
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

  const preview = (
    showPreview && contentResult && (
      <ImageViewport blob={contentResult} isOpen={true} onClose={onClose}/>
    )
  );

  const body = (
    <TailwindContents>
      <div className="flex items-center gap-4 group">
        {iconAndText}
        {preview}
        <div className="opacity-0 group-hover:opacity-100">
          <DownloadButton isDownloading={isDownloading} doSave={doSave} />
        </div>
      </div>
    </TailwindContents>
  );


  const previewComponent = (result: Blob) => {
    return <ImageThumbnail blob={result} onClick={onTextClick}/>
  }

  const tooltipPreview = (

    <CreateToolTipPreview
      onClick={onTextClick}
      previewComponent={previewComponent}
      isDownloading={isDownloading}
      setIsDownloading={(val) => {setIsDownloading(val)}}
      contentResult={contentResult}
    />
  )
  return {
    body,
    tooltipHint: 'Click icon or filename to preview, button to download',
    tooltipPreview
  };
};

export const handleGenericMimetype = ({
  iconStart,
  filename,
  isDownloading,
  doSave,
}: HandlerProps) => {
  const iconAndText = (
    <>
      {iconStart}
      <span>{filename}</span>
    </>
  );

  const body = (
    <TailwindContents>
      <div className="flex items-center gap-4 group">
        {iconAndText}
        <div className="opacity-0 group-hover:opacity-100">
          <DownloadButton isDownloading={isDownloading} doSave={doSave} />
        </div>
      </div>
    </TailwindContents>
  );

  return {
    body,
    tooltipHint: 'Click button to download',
  };
}

export const handleMimetype = ({mimetype, ...handlerProps}: HandlerProps): HandlerReturnType => {
  if (mimetype === 'application/pdf') {
    return handlePDFMimetype({mimetype, ...handlerProps})
  } else if (mimetype.startsWith('audio/')) {
    return handleAudioMimetype({mimetype, ...handlerProps})
  } else if (mimetype.startsWith('video/')) {
    return handleVideoMimetype({mimetype, ...handlerProps})
  } else if (mimetype.startsWith('image/')) {
    return handleImageMimetype({mimetype, ...handlerProps})
  } else {
    return handleGenericMimetype({mimetype, ...handlerProps})
  }
}
