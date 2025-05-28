import {Button} from '@wandb/weave/components/Button';
import {Tooltip} from '@wandb/weave/components/Tooltip';
import React, {Ref, RefObject, useCallback, useEffect, useRef, useState} from 'react';

import {convertBytes} from '../../../../../../util';
import {Icon, IconName, IconNames} from '../../../../../Icon';
import {LoadingDots} from '../../../../../LoadingDots';
import {TailwindContents} from '../../../../../Tailwind';
import {CustomLink} from '../../pages/common/Links';
import {useWFHooks} from '../../pages/wfReactInterface/context';
import {CustomWeaveTypePayload} from '../customWeaveType.types';
import {PDFView} from './PDFView';
import {VideoPopup, VideoThumbnail} from './VideoView';
import {MiniAudioViewer} from './AudioView';

const ICON_MAP: Record<string, IconName> = {
  'application/json': IconNames.JobProgramCode,
  'text/csv': IconNames.Table,
  'text/html': IconNames.JobProgramCode,
  'text/xml': IconNames.JobProgramCode,
};

const getIconName = (mimetype: string): IconName => {
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

// Save a Blob as a content in the user's downloads folder in a
// cross-browser compatible way.
const saveBlob = (blob: Blob, filename: string) => {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  });
};

type ContentTypePayload = CustomWeaveTypePayload<
  'weave.type_wrappers.Content.content.Content',
  {content: string; 'metadata.json': string}
>;

type ContentViewProps = {
  entity: string;
  project: string;
  mode?: string;
  data: ContentTypePayload;
};

type ContentMetadata = {
  original_path?: string;
  mimetype: string;
  size: number;
  filename: string;
};

export const ContentView = ({entity, project, data}: ContentViewProps) => {
  const {useFileContent} = useWFHooks();
  const metadata = useFileContent({
    entity,
    project,
    digest: data.files['metadata.json'],
  });

  if (metadata.loading) {
    return <LoadingDots />;
  }
  // TODO: Should add an explicit error condition to useFileContent
  if (metadata.result == null) {
    return <span>Metadata not found</span>;
  }

  // Convert ArrayBuffer to JSON
  let metadataJson;
  try {
    const decoder = new TextDecoder();
    const jsonString = decoder.decode(metadata.result);
    metadataJson = JSON.parse(jsonString);
  } catch (error) {
    console.error('Error parsing metadata JSON:', error);
    return <span>Error parsing metadata</span>;
  }

  const content = data.files['content'];
  return (
    <ContentViewMetadataLoaded
      entity={entity}
      project={project}
      metadata={metadataJson}
      content={content}
    />
  );
};

type ContentViewMetadataLoadedProps = {
  entity: string;
  project: string;
  metadata: ContentMetadata;
  content: string;
};

const ContentViewMetadataLoaded = ({
  entity,
  project,
  metadata,
  content,
}: ContentViewMetadataLoadedProps) => {
  const [contentResult, setContentResult] = useState<Blob | null>(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const [showPreview, setShowPreview] = useState(false);

  const {useFileContent} = useWFHooks();
  const {filename, size, mimetype} = metadata;

  const iconStart = <Icon name={getIconName(mimetype)} />;
  const contentContent = useFileContent({
    entity,
    project,
    digest: content,
    skip: !isDownloading,
  });

  // Store the last non-null content content result in state
  // We do this because passing skip: true to useFileContent will
  // result in contentContent.result getting returned as null even
  // if it was previously downloaded successfully.
  useEffect(() => {
    if (contentContent.result) {
      const blob = new Blob([contentContent.result], {
        type: mimetype,
      });

      setContentResult(blob);
      setIsDownloading(false);
    }
  }, [contentContent.result, mimetype]);

  const doSave = useCallback(() => {
    if (!contentResult) {
      console.error('No content result');
      return;
    }
    saveBlob(contentResult, filename);
  }, [contentResult, filename]);

  const downloadContent = () => {
    if(!contentResult && !isDownloading) { setIsDownloading(true); }
    else if(contentResult) { console.log('Already Downloaded!') }
  }

  const openPreview = () => {
    setShowPreview(true);
    if (!contentResult && !isDownloading) {
      downloadContent()
    }
  };
  const closePreview = () => {
    setShowPreview(false)
  }


  let tooltipHint = 'Click button to download';
  let body = null
  let iconAndText = (
    <>
      {iconStart}
      <span>{filename}</span>
    </>
  );
  if (mimetype === 'application/pdf') {
    iconAndText = (
      <>
        <CustomLink
          variant="secondary"
          icon={iconStart}
          onClick={openPreview}
          text={filename}
        />
        {showPreview && contentResult && (
          <PDFView
            open={true}
            onClose={closePreview}
            blob={contentResult}
            onDownload={doSave}
          />
        )}
      </>
    );
    tooltipHint = 'Click icon or filename to preview, button to download';
  }
  if (mimetype.startsWith('audio/')) {
    const onTextClick = () => {
      setShowPreview(true);
      if (!contentResult) {
        setIsDownloading(true);
      }
    };

    iconAndText = (
      <>
        {!showPreview && <CustomLink
            variant="secondary"
            icon={iconStart}
            onClick={onTextClick}
            text={filename}
          />
        }
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
    tooltipHint = 'Click icon or filename to preview, button to download';
  }

  if (mimetype.startsWith('video/')) {
    let videoRef = useRef<HTMLVideoElement>(null)
    const onTextClick = () => {
      setShowPreview(true);
      if (!contentResult) {
        setIsDownloading(true);
      }
    };

    const onClose = () => {
      setShowPreview(false);
    };

    iconAndText = (
      <>
        <CustomLink
          variant="secondary"
          icon={iconStart}
          onClick={onTextClick}
          text={filename}
        />
        {showPreview && contentResult && (
          <VideoPopup
            src={contentResult}
            isOpen={true}
            onClose={onClose}
            videoRef={videoRef}
          />
        )}
      </>
    );
    tooltipHint = 'Click icon or filename to preview, button to download';
  }
  const tooltip = (
    <TailwindContents>
      <div className="grid grid-cols-[auto_auto] items-center gap-x-2 gap-y-1">
        <div className="text-right font-bold">Name</div>
        <div>{filename}</div>
        <div className="text-right font-bold">MIME type</div>
        <div>{mimetype}</div>
        <div className="text-right font-bold">Size</div>
        <div>{convertBytes(size)}</div>
      </div>
      {tooltipHint && (
        <div className="text-sm">
          <div className="mt-8 text-center text-xs">{tooltipHint}</div>
        </div>
      )}
    </TailwindContents>
  );

  body = (
    <TailwindContents>
      <div className="flex items-center gap-4 group">
        {iconAndText}
          <div className="opacity-0 group-hover:opacity-100">
            <Button
              icon={isDownloading ? 'loading' : 'download'}
              variant="ghost"
              size="small"
              onClick={isDownloading ? undefined : doSave}
            />
        </div>
      </div>
    </TailwindContents>
  )
  return (
    <>
      {showPreview && body}
      {!showPreview && (<Tooltip trigger={body} content={tooltip} />)}
    </>
  )
};
