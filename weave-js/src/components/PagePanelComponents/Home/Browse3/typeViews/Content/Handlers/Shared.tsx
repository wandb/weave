import {IconName, IconNames} from '@wandb/weave/components/Icon';

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

