import * as Dialog from '@wandb/weave/components/Dialog/Dialog';
import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {useEffect, useMemo, useState} from 'react';

type ImageViewProps = {
  blob: Blob;
  containerWidth?: number;
  containerHeight?: number;
};

type ImageViewportProps = {
  blob: Blob;
  isOpen: boolean;
  onClose: () => void;
};

type ImageThumbnailProps = ImageViewProps & {
  blob: Blob;
  onClick: () => void;
  thumbnailHeight?: number;
  thumbnailWidth?: number;
};

const loadImage = (setImageDim: any, imageUrl: string) => {
  const img = new Image();
  img.src = imageUrl;

  img.onload = () => {
    setImageDim({
      height: img.height,
      width: img.width,
    });
  };
  img.onerror = err => {
    console.error(err);
  };
};

export const ImageThumbnail = ({
  blob,
  onClick,
  thumbnailHeight,
  thumbnailWidth,
}: ImageThumbnailProps) => {
  const url = useMemo(() => {
    return URL.createObjectURL(blob);
  }, [blob]);

  useEffect(() => {
    return () => {
      URL.revokeObjectURL(url);
    };
  }, [url]);

  thumbnailHeight = thumbnailHeight ?? 38 * 3; // Default height of the cell row
  thumbnailWidth = thumbnailWidth ?? 68 * 3; // 16:9-ish ratio

  return (
    <Tailwind>
      <div
        className="relative flex h-full w-full items-center justify-start"
        style={{cursor: 'pointer'}}
        onClick={onClick}>
        <div
          style={{height: thumbnailHeight, width: thumbnailWidth}}
          className="relative">
          <img
            style={{
              width: '100%',
              height: '100%',
              objectFit: 'contain',
            }}
            src={url}
            alt="Preview Thumbnail"
          />
          <div className="absolute inset-0 flex items-center justify-center bg-oblivion/30 transition-all duration-200 hover:bg-oblivion/10">
            <span className="text-xs text-white">🔍</span>
          </div>
        </div>
      </div>
    </Tailwind>
  );
};
export const ImageViewport = ({blob, isOpen, onClose}: ImageViewportProps) => {
  const [imageDim, setImageDim] = useState({width: -1, height: -1});

  const url = useMemo(() => {
    return URL.createObjectURL(blob);
  }, [blob]);

  useEffect(() => {
    setImageDim({width: -1, height: -1});
    loadImage(setImageDim, url);
    return () => {
      URL.revokeObjectURL(url);
    };
  }, [url]);

  if (imageDim.width === -1 || imageDim.height === -1) {
    return <LoadingDots />;
  }

  return (
    <Dialog.Root open={isOpen} onOpenChange={onClose}>
      <Dialog.Portal>
        <Dialog.Overlay />
        <Dialog.Content className="p-0">
          <div
            style={{
              width: '100%',
              height: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
            <img
              style={{
                maxWidth: '100%',
                maxHeight: '100%',
                objectFit: 'contain',
              }}
              src={url}
              alt="Popup Preview"
            />
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
};
