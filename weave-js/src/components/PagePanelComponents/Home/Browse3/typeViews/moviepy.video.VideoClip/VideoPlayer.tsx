import * as Dialog from '@wandb/weave/components/Dialog/Dialog';
import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import {NotApplicable} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/NotApplicable';
import {CustomLink} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/common/Links';
import {useWFHooks} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/context';
import {CustomWeaveTypePayload} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/typeViews/customWeaveType.types';
import {CustomWeaveTypeProjectContext} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/typeViews/CustomWeaveTypeDispatcher';
import VideoViewer from '@wandb/weave/components/Panel2/VideoViewer';
import React, {useContext, useEffect, useState} from 'react';
import {AutoSizer} from 'react-virtualized';

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

export const VideoPlayer: React.FC<VideoPlayerProps> = props => (
  <AutoSizer style={{height: '100%', width: '100%'}}>
    {({width, height}) =>
      width === 0 || height === 0 ? null : (
        <VideoPlayerWithSize
          {...props}
          containerWidth={width}
          containerHeight={height}
        />
      )
    }
  </AutoSizer>
);

type VideoPlayerWithSizeProps = VideoPlayerProps & {
  containerWidth: number;
  containerHeight: number;
};

const VideoPlayerWithSize: React.FC<VideoPlayerWithSizeProps> = ({
  entity,
  project,
  data,
  containerWidth,
  containerHeight,
  mode: propMode,
}) => {
  const [showPopup, setShowPopup] = useState(false);
  const {useFileContent} = useWFHooks();
  const context = useContext(CustomWeaveTypeProjectContext);
  const mode = propMode ?? context?.mode;

  // Find the first available video format
  const videoKey = Object.keys(data.files).find(key => key in VIDEO_TYPES) as
    | VideoFileKeys
    | undefined;

  // Always call the hook with consistent arguments
  const videoBinary = useFileContent(
    entity,
    project,
    videoKey ? data.files[videoKey] : '',
    {skip: !videoKey}
  );

  if (!videoKey) {
    return <NotApplicable />;
  }

  const fileExt = VIDEO_TYPES[videoKey];
  const title = data.custom_name || entity.split('-')[0];

  // Link mode (default view)
  if (!mode || mode !== 'object_viewer' || containerHeight < 50) {
    const videoText = `${fileExt.toUpperCase()} Video`;

    return (
      <>
        <div className="flex h-full w-full items-center justify-start">
          <CustomLink
            text={videoText}
            fontWeight={400}
            onClick={() => setShowPopup(true)}
          />
        </div>

        {showPopup && videoBinary.result && (
          <Dialog.Root open={showPopup} onOpenChange={setShowPopup}>
            <Dialog.Portal>
              <Dialog.Overlay />
              <Dialog.Content className="h-[60vh] w-[60vw] p-0">
                <VideoContent
                  fileExt={fileExt}
                  buffer={videoBinary.result}
                  containerWidth={containerWidth}
                  containerHeight={containerHeight}
                  title={title}
                />
              </Dialog.Content>
            </Dialog.Portal>
          </Dialog.Root>
        )}
      </>
    );
  }

  // Full viewer mode
  if (videoBinary.loading) {
    return <LoadingDots />;
  }

  if (videoBinary.result == null) {
    return <span />;
  }

  return (
    <VideoContent
      fileExt={fileExt}
      buffer={videoBinary.result}
      containerWidth={containerWidth}
      containerHeight={containerHeight}
      title={title}
    />
  );
};

type VideoContentProps = {
  fileExt: VideoFormat;
  buffer: ArrayBuffer;
  containerWidth: number;
  containerHeight: number;
  title: string;
  previewImageUrl?: string;
};

const VideoContent: React.FC<VideoContentProps> = ({
  fileExt,
  buffer,
  containerWidth,
  containerHeight,
  title,
  previewImageUrl,
}) => {
  const [url, setUrl] = useState<string>('');

  useEffect(() => {
    const mimeType = MIME_TYPES[fileExt];
    const blob = new Blob([buffer], {type: mimeType});
    const objectUrl = URL.createObjectURL(blob);
    setUrl(objectUrl);

    return () => URL.revokeObjectURL(objectUrl);
  }, [buffer, fileExt]);

  if (!url) {
    return <LoadingDots />;
  }

  return containerHeight >= 1 ? (
    <VideoViewer
      videoSrc={url}
      width={containerWidth}
      height={containerHeight}
    />
  ) : null;
};
