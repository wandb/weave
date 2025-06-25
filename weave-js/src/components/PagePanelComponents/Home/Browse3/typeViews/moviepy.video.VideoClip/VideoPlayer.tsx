import {NotApplicable} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/NotApplicable';
import {CustomWeaveTypePayload} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/typeViews/customWeaveType.types';
import React from 'react';

import {ContentMetadata} from '../Content/types';
import {VideoContent} from '../Content/VideoView';

type VideoFormat = 'gif' | 'mp4' | 'webm';
type VideoFileKeys = `video.${VideoFormat}`;

type VideoClipTypePayload = CustomWeaveTypePayload<
  'moviepy.video.VideoClip.VideoClip',
  {[K in VideoFileKeys]: string}
>;

type VideoPlayerProps = {
  entity: string;
  project: string;
  mode?: string;
  data: VideoClipTypePayload;
};

const VIDEO_TYPES: Record<VideoFileKeys, VideoFormat> = {
  'video.gif': 'gif',
  'video.mp4': 'mp4',
  'video.webm': 'webm',
};

const MIME_TYPES: Record<VideoFormat, string> = {
  gif: 'image/gif',
  mp4: 'video/mp4',
  webm: 'video/webm',
};

export const VideoPlayer: React.FC<VideoPlayerProps> = ({
  entity,
  project,
  mode,
  data,
}) => {
  // Find the first available video format
  const videoKey = Object.keys(data.files).find(key => key in VIDEO_TYPES) as
    | VideoFileKeys
    | undefined;

  if (!videoKey) {
    return <NotApplicable />;
  }

  const fileExt = VIDEO_TYPES[videoKey];
  const mimeType = MIME_TYPES[fileExt];
  const title = data.custom_name || entity.split('-')[0];

  // Create metadata to match Content type structure
  const metadata: ContentMetadata = {
    filename: title,
    mimetype: mimeType,
    size: 0, // Size not available in video clip data
  };

  return (
    <VideoContent
      entity={entity}
      project={project}
      mode={mode}
      metadata={metadata}
      content={data.files[videoKey]}
    />
  );
};
