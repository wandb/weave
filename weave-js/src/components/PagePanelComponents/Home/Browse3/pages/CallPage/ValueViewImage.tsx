import 'yet-another-react-lightbox/styles.css';

import React, {useEffect, useState} from 'react';
import Lightbox from 'yet-another-react-lightbox';
import Fullscreen from 'yet-another-react-lightbox/plugins/fullscreen';
import Zoom from 'yet-another-react-lightbox/plugins/zoom';

import {LoadingDots} from '../../../../../LoadingDots';
import {Tooltip} from '../../../../../Tooltip';

type ValueViewImageProps = {
  value: string;
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
    console.log('img error');
    console.error(err);
  };
};

export const ValueViewImage = ({value}: ValueViewImageProps) => {
  const maxDim = 200;
  const [imageDim, setImageDim] = useState({
    width: -1,
    height: -1,
  });
  const [lightboxOpen, setLightboxOpen] = useState(false);

  useEffect(() => {
    setImageDim({width: -1, height: -1});
    loadImage(setImageDim, value);
  }, [value]);

  if (imageDim.width === -1 || imageDim.height === -1) {
    return <LoadingDots />;
  }

  const maxImageDim = Math.max(imageDim.width, imageDim.height);
  const isThumbnail = maxImageDim > maxDim;
  const alt = `Logged image ${imageDim.width}x${imageDim.height}px`;
  if (!isThumbnail) {
    return <img src={value} alt={alt} />;
  }

  // Image was too big for space, show a thumbnail and open lightbox on click.
  const onClick = () => setLightboxOpen(true);
  const ratio = maxDim / maxImageDim;
  const w = imageDim.width * ratio;
  const h = imageDim.height * ratio;

  return (
    <>
      <Tooltip
        content="Click to view large"
        trigger={
          <img
            style={{cursor: 'pointer'}}
            src={value}
            width={w}
            height={h}
            alt={alt}
            onClick={onClick}
          />
        }
      />
      <Lightbox
        plugins={[Fullscreen, Zoom]}
        open={lightboxOpen}
        close={() => setLightboxOpen(false)}
        controller={{
          closeOnBackdropClick: true,
        }}
        slides={[{src: value}]}
        render={{
          // Hide previous and next buttons because we only have one image.
          buttonPrev: () => null,
          buttonNext: () => null,
        }}
        carousel={{finite: true}}
      />
    </>
  );
};
