
import * as Dialog from '@wandb/weave/components/Dialog/Dialog';
import {IconPlay} from '@wandb/weave/components/Icon';
import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {useEffect, useMemo, useRef, useState} from 'react';

type VideoPreviewProps = {
  src: Blob | string;
  videoRef: React.RefObject<HTMLVideoElement>;
  onClick: () => void;
};

type VideoPopupProps = {
  src: Blob | string;
  videoRef: React.RefObject<HTMLVideoElement>;
  isOpen: boolean;
  onClose: () => void;
};

const VideoPreview: React.FC<VideoPreviewProps> = ({
  src,
  videoRef,
  onClick,
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
    <Tailwind>
      <div
        className="relative flex h-full w-full items-center justify-start"
        style={{cursor: 'pointer'}}
        onClick={onClick}>
        <div
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
  src,
  isOpen,
  videoRef,
  onClose,
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
