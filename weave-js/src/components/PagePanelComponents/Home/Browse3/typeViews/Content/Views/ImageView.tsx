import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {useEffect, useMemo, useState} from 'react';
import Lightbox from 'yet-another-react-lightbox';
import Fullscreen from 'yet-another-react-lightbox/plugins/fullscreen';
import Zoom from 'yet-another-react-lightbox/plugins/zoom';

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
  height?: number | string;
  width?: number | string;
};


type PeekingImageThumbailProps = ImageViewProps & {
  blob: Blob;
  onClick: () => void;
  height: number | string;
  width: number | string;
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

export const PeekingImageThumbnail = ({
  blob,
  onClick,
  height,
  width,
}: PeekingImageThumbailProps) => {
  // In cell preview
  if (height < 24) {
    height = 38;
    width = 68;
  }
  else {
    height = "100%";
    width = "100%";
  }

  return <ImageThumbnail blob={blob} onClick={onClick} height={height} width={width} />;
};

export const ImageThumbnail = ({
  blob,
  onClick,
  height,
  width,
}: ImageThumbnailProps) => {
  const url = useMemo(() => {
    return URL.createObjectURL(blob);
  }, [blob]);

  useEffect(() => {
    return () => {
      URL.revokeObjectURL(url);
    };
  }, [url]);

  const thumbnailHeight = height ?? 38 * 3; // Default height of the cell row
  const thumbnailWidth = width ?? 68 * 3; // 16:9-ish ratio

  // For small previews, use fixed dimensions to prevent jumping
  const isSmallPreview = typeof height === 'number' && height <= 38;
  
  return (
    <Tailwind>
      <div
        className={`relative flex items-center justify-start ${isSmallPreview ? '' : 'h-full w-full'}`}
        style={{
          cursor: 'pointer',
          ...(isSmallPreview && {
            height: thumbnailHeight,
            width: thumbnailWidth,
            flexShrink: 0
          })
        }}
        onClick={onClick}>
        <div
          style={{
            height: isSmallPreview ? '100%' : thumbnailHeight,
            width: isSmallPreview ? '100%' : thumbnailWidth
          }}
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
    <>
      <Lightbox
        plugins={[Fullscreen, Zoom]}
        open={isOpen}
        close={onClose}
        controller={{
          closeOnBackdropClick: true,
        }}
        slides={[{src: url}]}
        render={{
          // Hide previous and next buttons because we only have one image.
          buttonPrev: () => null,
          buttonNext: () => null,
        }}
        carousel={{finite: true}}
        zoom={{maxZoomPixelRatio: 5}}
      />
    </>
  );
};
