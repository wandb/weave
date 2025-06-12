import * as Dialog from '@wandb/weave/components/Dialog/Dialog';
import {IconPlay} from '@wandb/weave/components/Icon';
import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import {WeaveflowPeekContext} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/context';
import {NotApplicable} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/NotApplicable';
import {useWFHooks} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/context';
import {CustomWeaveTypePayload} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/typeViews/customWeaveType.types';
import {CustomWeaveTypeProjectContext} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/typeViews/CustomWeaveTypeDispatcher';
import {Pill} from '@wandb/weave/components/Tag';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import {Tooltip} from '@wandb/weave/components/Tooltip';
import React, {useContext, useEffect, useMemo, useRef, useState} from 'react';
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
  const {isPeeking} = useContext(WeaveflowPeekContext);
  const mode = propMode ?? context?.mode;
  const videoRef = useRef<HTMLVideoElement>(null);

  // Find the first available video format
  const videoKey = Object.keys(data.files).find(key => key in VIDEO_TYPES) as
    | VideoFileKeys
    | undefined;

  // Always call the hook with consistent arguments
  const digest = useMemo(
    () => (videoKey ? data.files[videoKey] : ''),
    [videoKey, data.files]
  );
  const videoBinary = useFileContent({
    entity,
    project,
    digest,
    skip: !videoKey,
  });

  if (!videoKey) {
    return <NotApplicable />;
  }

  const fileExt = VIDEO_TYPES[videoKey];
  const title = data.custom_name || entity.split('-')[0];

  // Link mode (default view)
  if (!mode || mode !== 'object_viewer' || containerHeight < 50) {
    const videoText = `${fileExt.toUpperCase()}`;

    // Show thumbnail in drawer view, link in list view
    if (isPeeking) {
      const thumbnailHeight = Math.min(containerHeight, 38); // Default height of the cell row
      const thumbnailWidth = Math.min(containerWidth, 68); // 16:9-ish ratio

      const thumbnailContent = (
        <Tailwind>
          <div
            className="relative flex h-full w-full items-center justify-start"
            style={{cursor: 'pointer'}}
            onClick={() => setShowPopup(true)}>
            <div
              style={{height: thumbnailHeight, width: thumbnailWidth}}
              className="relative">
              {videoBinary.result ? (
                <>
                  <VideoContent
                    fileExt={fileExt}
                    buffer={videoBinary.result}
                    containerWidth={thumbnailWidth}
                    containerHeight={thumbnailHeight}
                    title={title}
                    isThumbnail={true}
                    videoRef={videoRef}
                  />
                  <div className="absolute inset-0 flex items-center justify-center bg-oblivion/30 transition-all duration-200 hover:bg-oblivion/10">
                    <IconPlay className="text-white" />
                  </div>
                </>
              ) : (
                <LoadingDots />
              )}
            </div>
          </div>
        </Tailwind>
      );

      return (
        <>
          <Tooltip
            trigger={thumbnailContent}
            content={`${fileExt.toUpperCase()} Video - Click to play`}
          />

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
                    videoRef={videoRef}
                  />
                </Dialog.Content>
              </Dialog.Portal>
            </Dialog.Root>
          )}
        </>
      );
    } else {
      // List view - show simple link
      return (
        <div className="flex h-full w-full items-center justify-start">
          <div className="cursor-pointer" onClick={() => setShowPopup(true)}>
            <Pill
              label={videoText}
              icon="play"
              color="moon"
              isInteractive={true}
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
                    videoRef={videoRef}
                  />
                </Dialog.Content>
              </Dialog.Portal>
            </Dialog.Root>
          )}
        </div>
      );
    }
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
      videoRef={videoRef}
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
  isThumbnail?: boolean;
  videoRef: React.RefObject<HTMLVideoElement>;
};

const VideoContent: React.FC<VideoContentProps> = ({
  fileExt,
  buffer,
  containerWidth,
  containerHeight,
  title,
  previewImageUrl,
  isThumbnail,
  videoRef,
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
    <div
      style={{
        width: '100%',
        height: '100%',
        overflow: 'hidden',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}>
      <video
        ref={videoRef}
        src={url}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'contain',
        }}
        controls={!isThumbnail}
        autoPlay={false}
        muted={true}
        loop={isThumbnail}
        onLoadedData={() => {
          if (isThumbnail && videoRef.current) {
            // For thumbnails, seek to 1 second or 25% of the video duration
            const seekTime = Math.min(1, videoRef.current.duration * 0.25);
            videoRef.current.currentTime = seekTime;
          }
        }}
      />
    </div>
  ) : null;
};
