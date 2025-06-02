import {IconName, IconNames} from '@wandb/weave/components/Icon';
import {Tooltip} from '@wandb/weave/components/Tooltip';
import {TailwindContents} from '@wandb/weave/components/Tailwind';
import {convertBytes} from '@wandb/weave/util';
import React from 'react';

const ICON_MAP: Record<string, IconName> = {
  'application/json': IconNames.JobProgramCode,
  'text/csv': IconNames.Table,
  'text/html': IconNames.JobProgramCode,
  'text/xml': IconNames.JobProgramCode,
  'audio': IconNames.MusicAudio,
  'image': IconNames.Photo,
  'video': IconNames.VideoPlay,
  'text': IconNames.Document,
};

export const getIconName = (mimetype: string): IconName => {
  const iconName = ICON_MAP[mimetype];
  const [type] = mimetype.split('/', 2);
  return iconName ?? ICON_MAP[type] ?? IconNames.Document;
};


export type HandlerProps = {
  mimetype: string;
  filename: string;
  size: number;
  iconStart: React.ReactNode;
  showPreview: boolean;
  isDownloading: boolean;
  containerWidth: number,
  containerHeight: number,
  contentResult: Blob | null;
  openPreview: () => void;
  closePreview: () => void;
  doSave: () => void;
  setShowPreview: (show: boolean) => void;
  setIsDownloading: (downloading: boolean) => void;
  videoPlaybackState?: {currentTime: number; volume: number; muted: boolean};
  updateVideoPlaybackState?: (
    newState: Partial<{currentTime: number; volume: number; muted: boolean}>
  ) => void;
};


export type HandlerReturnType = {
  body: React.ReactNode;
  tooltipHint: string;
  tooltipPreview?: React.ReactNode;
};

type ContentTooltipWrapperProps = {
  showPreview: boolean;
  tooltipHint?: string;
  tooltipPreview?: React.ReactNode;
  body: React.ReactNode;
  children: React.ReactNode;
};

export const ContentTooltipWrapper = ({
  showPreview,
  tooltipHint,
  tooltipPreview,
  body,
  children,
}: ContentTooltipWrapperProps) => {
  const tooltip = (
    <TailwindContents>
      {tooltipPreview && (
        <div className="flex justify-center">{tooltipPreview}</div>
      )}
      {!tooltipPreview && children}
      {tooltipHint && (
        <div className="text-sm">
          <div className="mt-8 text-center text-xs">{tooltipHint}</div>
        </div>
      )}
    </TailwindContents>
  );

  return (
    <>
      {showPreview && body}
      {!showPreview && <Tooltip trigger={body} content={tooltip} />}
    </>
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

