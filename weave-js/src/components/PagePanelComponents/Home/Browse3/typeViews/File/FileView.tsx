import {Button} from '@wandb/weave/components/Button';
import {Tooltip} from '@wandb/weave/components/Tooltip';
import React, {useCallback, useEffect, useState} from 'react';

import {convertBytes} from '../../../../../../util';
import {Icon, IconName, IconNames} from '../../../../../Icon';
import {LoadingDots} from '../../../../../LoadingDots';
import {TailwindContents} from '../../../../../Tailwind';
import {CustomLink} from '../../pages/common/Links';
import {useWFHooks} from '../../pages/wfReactInterface/context';
import {CustomWeaveTypePayload} from '../customWeaveType.types';
import {PDFView} from './PDFView';

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

// Save a Blob as a file in the user's downloads folder in a
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

type FileTypePayload = CustomWeaveTypePayload<
  'weave.type_handlers.File.file.File',
  {file: string; 'metadata.json': string}
>;

type FileViewProps = {
  entity: string;
  project: string;
  mode?: string;
  data: FileTypePayload;
};

type FileMetadata = {
  original_path: string;
  mimetype: string;
  size: number;
};

export const FileView = ({entity, project, data}: FileViewProps) => {
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

  const file = data.files['file'];
  return (
    <FileViewMetadataLoaded
      entity={entity}
      project={project}
      metadata={metadataJson}
      file={file}
    />
  );
};

type FileViewMetadataLoadedProps = {
  entity: string;
  project: string;
  metadata: FileMetadata;
  file: string;
};

const FileViewMetadataLoaded = ({
  entity,
  project,
  metadata,
  file,
}: FileViewMetadataLoadedProps) => {
  const [fileResult, setFileResult] = useState<Blob | null>(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const [showPreview, setShowPreview] = useState(false);

  const {useFileContent} = useWFHooks();
  const {original_path, size, mimetype} = metadata;

  const iconStart = <Icon name={getIconName(mimetype)} />;
  const filename = original_path.split('/').pop() || original_path;
  const onDownloadCallback = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDownloading(true);
  }, []);
  const fileContent = useFileContent({
    entity,
    project,
    digest: file,
    skip: !isDownloading,
  });

  // Store the last non-null file content result in state
  // We do this because passing skip: true to useFileContent will
  // result in fileContent.result getting returned as null even
  // if it was previously downloaded successfully.
  useEffect(() => {
    if (fileContent.result) {
      const blob = new Blob([fileContent.result], {
        type: mimetype,
      });

      setFileResult(blob);
      setIsDownloading(false);
    }
  }, [fileContent.result, mimetype]);

  const doSave = useCallback(() => {
    if (!fileResult) {
      console.error('No file result');
      return;
    }
    saveBlob(fileResult, filename);
  }, [fileResult, filename]);

  useEffect(() => {
    // If we have finished downloading the file and the
    // user action wasn't opening a preview, save it.
    if (fileResult && !isDownloading && !showPreview) {
      doSave();
    }
    // Don't want a showPreview dependency because we don't want to save on preview close
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fileResult, isDownloading, doSave]);

  const onClickDownload = isDownloading ? undefined : onDownloadCallback;

  let tooltipHint = 'Click button to download';
  let iconAndText = (
    <>
      {iconStart}
      <span>{filename}</span>
    </>
  );
  if (mimetype === 'application/pdf') {
    const onTextClick = () => {
      setShowPreview(true);
      if (!fileResult) {
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
        {showPreview && fileResult && (
          <PDFView
            open={true}
            onClose={onClose}
            blob={fileResult}
            onDownload={doSave}
          />
        )}
      </>
    );
    tooltipHint = 'Click icon or filename to preview, button to download';
  }

  const body = (
    <TailwindContents>
      <div className="flex items-center gap-4">
        {iconAndText}
        <Button
          icon={isDownloading ? 'loading' : 'download'}
          variant="ghost"
          size="small"
          onClick={onClickDownload}
        />
      </div>
    </TailwindContents>
  );

  // No need to compute the tooltip, we don't want it showing over the preview anyway.
  if (showPreview) {
    return body;
  }

  const tooltip = (
    <TailwindContents>
      <div className="grid grid-cols-[auto_auto] items-center gap-x-2 gap-y-1">
        <div className="text-right font-bold">Name</div>
        <div>{original_path}</div>
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

  return <Tooltip trigger={body} content={tooltip} />;
};
