import {Button} from '@wandb/weave/components/Button';
import {StyledTooltip} from '@wandb/weave/components/DraggablePopups';
import {Icon, IconName, IconNames} from '@wandb/weave/components/Icon';
import {CustomLink} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/common/Links';
import {TailwindContents} from '@wandb/weave/components/Tailwind';
import {convertBytes} from '@wandb/weave/util';
import React from 'react';

import {ContentMetadata} from './types';

const ICON_MAP: Record<string, IconName> = {
  'application/json': IconNames.JobProgramCode,
  'text/csv': IconNames.Table,
  'text/html': IconNames.JobProgramCode,
  'text/xml': IconNames.JobProgramCode,
  audio: IconNames.MusicAudio,
  image: IconNames.Photo,
  video: IconNames.VideoPlay,
  text: IconNames.Document,
};

export const getIconName = (mimetype: string): IconName => {
  const iconName = ICON_MAP[mimetype];
  const [type] = mimetype.split('/', 2);
  return iconName ?? ICON_MAP[type] ?? IconNames.Document;
};

export const DownloadButton = ({
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

// Memoized component that doesn't re-render on size changes
export const IconWithText = ({
  iconName,
  filename,
  onClick,
}: {
  iconName: IconName;
  filename: string;
  onClick?: () => void;
}) => {
  const icon = <Icon name={iconName} />;
  if (onClick) {
    return (
      <CustomLink
        variant="secondary"
        icon={icon}
        onClick={onClick}
        text={filename}
      />
    );
  }

  return (
    <div className="flex items-center gap-2">
      <Icon name={iconName} />
      <span>{filename}</span>
    </div>
  );
};

type ContentMetadataTooltipProps = {
  filename: string;
  mimetype: string;
  size: number;
};

export const ContentMetadataTooltip = ({
  filename,
  mimetype,
  size,
}: ContentMetadataTooltipProps) => {
  return (
    <div className="grid grid-cols-[auto_auto] items-center gap-x-2 gap-y-1">
      <div className="text-right font-bold">Name</div>
      <div>{filename}</div>
      <div className="text-right font-bold">MIME type</div>
      <div>{mimetype}</div>
      <div className="text-right font-bold">Size</div>
      <div>{convertBytes(size)}</div>
    </div>
  );
};

// Save a Blob as a content in the user's downloads folder in a
// cross-browser compatible way.
export const saveBlob = (blob: Blob, filename: string) => {
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

// Download helper for URLs (used for video/audio that already have blob URLs)
export const downloadFromUrl = (url: string, filename: string) => {
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
};

export const IconWithTextAndDownloadHover = ({
  metadata,
  iconName,
  onClick,
  isDownloading,
  doSave,
}: {
  metadata: ContentMetadata;
  iconName: IconName;
  onClick?: () => void;
  isDownloading: boolean;
  doSave: () => void;
}) => {
  const {filename, size, mimetype} = metadata;
  const clickableIconAndText = (
    <div>
      <IconWithText iconName={iconName} filename={filename} onClick={onClick} />
    </div>
  );
  return (
    <TailwindContents>
      <div className="group flex items-center gap-4">
        <StyledTooltip
          enterDelay={500}
          title={
            <TailwindContents>
              <ContentMetadataTooltip
                filename={filename}
                mimetype={mimetype}
                size={size}
              />
              <div className="text-sm">
                <div className="mt-8 text-center text-xs">
                  Click icon or filename to preview, button to download
                </div>
              </div>
            </TailwindContents>
          }>
          {clickableIconAndText}
        </StyledTooltip>
        <div className="opacity-0 group-hover:opacity-100">
          <DownloadButton isDownloading={isDownloading} doSave={doSave} />
        </div>
      </div>
    </TailwindContents>
  );
};
