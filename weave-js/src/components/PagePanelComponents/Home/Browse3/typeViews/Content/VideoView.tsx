
import * as Dialog from '@wandb/weave/components/Dialog/Dialog';
import {IconPlay} from '@wandb/weave/components/Icon';
import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {useEffect, useMemo, useRef, useState} from 'react';

type VideoPreviewProps = {
  blob: Blob;
  containerHeight: number;
  containerWidth: number;
  videoRef: React.RefObject<HTMLVideoElement>;
  onShowPopup: () => void;
};

type VideoPopupProps = {
  url: string;
  videoRef: React.RefObject<HTMLVideoElement>;
  isOpen: boolean;
  onClose: () => void;
};

const VideoPreview: React.FC<VideoPreviewProps> = ({
  blob,
  containerHeight,
  containerWidth,
  videoRef,
  onShowPopup,
}) => {
  const [url, setUrl] = useState<string>('');

  useEffect(() => {
    const objectUrl = URL.createObjectURL(blob);
    setUrl(objectUrl);

    return () => URL.revokeObjectURL(objectUrl);
  }, [blob]);

  if (!url) {
    return <LoadingDots />;
  }

  return (
    <Tailwind>
      <div
        className="relative flex h-full w-full items-center justify-start"
        style={{cursor: 'pointer'}}
        onClick={onShowPopup}>
        <div
          style={{height: containerHeight, width: containerWidth}}
          className="relative">
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
              controls={false}
              autoPlay={false}
              muted={true}
              loop={true}
              onLoadedData={() => {
                if (videoRef.current) {
                  const seekTime = Math.min(1, videoRef.current.duration * 0.25);
                  videoRef.current.currentTime = seekTime;
                }
              }}
            />
          </div>
          <div className="absolute inset-0 flex items-center justify-center bg-oblivion/30 transition-all duration-200 hover:bg-oblivion/10">
            <IconPlay className="text-white" />
          </div>
        </div>
      </div>
    </Tailwind>
  );
};

const VideoPopup: React.FC<VideoPopupProps> = ({
  url,
  isOpen,
  videoRef,
  onClose,
}) => {
  console.log(videoRef)

  return (
    <Dialog.Root open={isOpen} onOpenChange={onClose}>
      <Dialog.Portal>
        <Dialog.Overlay />
        <Dialog.Content className="h-[60vh] w-[60vw] p-0">
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
              controls={true}
              autoPlay={false}
              muted={true}
              onLoadedData={() => {
                if (videoRef.current) {
                  const seekTime = Math.min(1, videoRef.current.duration * 0.25);
                  videoRef.current.currentTime = seekTime;
                }
              }}
            />
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
};

export {VideoPreview, VideoPopup};
