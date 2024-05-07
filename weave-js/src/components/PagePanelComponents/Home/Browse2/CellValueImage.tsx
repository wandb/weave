import 'yet-another-react-lightbox/styles.css';

import React, {useState} from 'react';
import Lightbox from 'yet-another-react-lightbox';
import Fullscreen from 'yet-another-react-lightbox/plugins/fullscreen';
import Zoom from 'yet-another-react-lightbox/plugins/zoom';

import {Button} from '../../../Button/Button';

type CellValueImageProps = {
  value: string;
};

export const CellValueImage = ({value}: CellValueImageProps) => {
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const onClick = () => setLightboxOpen(true);

  const btn = (
    <Button
      variant="ghost"
      size="small"
      icon="photo"
      tooltip="Click to view"
      onClick={onClick}
    />
  );

  if (!lightboxOpen) {
    return btn;
  }

  return (
    <>
      {btn}
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
