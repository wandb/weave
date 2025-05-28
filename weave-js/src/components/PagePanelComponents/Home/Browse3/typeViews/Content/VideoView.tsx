
import * as Dialog from '@wandb/weave/components/Dialog/Dialog';
import {IconPlay} from '@wandb/weave/components/Icon';
import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {useEffect, useMemo, useRef, useState} from 'react';

type VideoProps = {
  src: Blob | string;
}
type VideoContentProps = {
  isThumbnail: boolean;
  videoRef: React.RefObject<HTMLVideoElement>;
  autoplay?: boolean;
} & VideoProps;

type VideoPreviewProps = {
  onClick: (() => void);
} & VideoProps;

type VideoPopupProps = {
  isOpen: boolean;
  onClose: (() => void);
} & VideoProps;

const VideoContent: React.FC<VideoContentProps> = ({
  src,
  isThumbnail,
  videoRef,
  autoplay
}) => {
  const [url, setUrl] = useState<string>('');

  useEffect(() => {
    if (src instanceof Blob) {
      const objectUrl = URL.createObjectURL(src);
      setUrl(objectUrl);
      return () => URL.revokeObjectURL(objectUrl);
    }
    else {
      setUrl(src)
      return
    }
  }, [src]);

  if (!url) {
    return <LoadingDots />;
  }

  return (
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
        autoPlay={autoplay ?? false}
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
  )
};


const VideoPopup: React.FC<VideoPopupProps> = ({
  src,
  isOpen,
  onClose
}) => {
  const videoRef = useRef<HTMLVideoElement>(null)
  return (
    <Dialog.Root open={isOpen} onOpenChange={onClose}>
      <Dialog.Portal>
        <Dialog.Overlay />
        <Dialog.Content className="h-[60vh] w-[60vw] p-0">
          <VideoContent
            src={src}
            videoRef={videoRef}
            isThumbnail={false}
            autoplay={false}
          />
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
const VideoThumbnail: React.FC<VideoPreviewProps> = ({
  src,
  onClick
}) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const thumbnailHeight = 38*3; // Default height of the cell row
  const thumbnailWidth = 68*3; // 16:9-ish ratio
  return (
    <Tailwind>
      <div
        className="relative flex h-full w-full items-center justify-start"
        style={{cursor: 'pointer'}}
        onClick={onClick}>
        <div
          style={{height: thumbnailHeight, width: thumbnailWidth}}
          className="relative">
          <VideoContent src={src} videoRef={videoRef} isThumbnail={true}/>
          <div className="absolute inset-0 flex items-center justify-center bg-oblivion/30 transition-all duration-200 hover:bg-oblivion/10">
            <IconPlay className="text-white" />
          </div>
        </div>
      </div>
    </Tailwind>
  );
}
export {VideoPopup,VideoThumbnail};


