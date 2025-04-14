import 'yet-another-react-lightbox/plugins/thumbnails.css';

import * as pdfjsLib from 'pdfjs-dist';
import React, {useEffect, useState} from 'react';
import Lightbox from 'yet-another-react-lightbox';
import Download from 'yet-another-react-lightbox/plugins/download';
import Thumbnails from 'yet-another-react-lightbox/plugins/thumbnails';
pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url
).toString();

type PDFViewerProps = {
  blob: Blob;
  open: boolean;
  onClose: () => void;
  onDownload?: () => void;
};

type PDFPageImage = {
  src: string;
};

export const PDFView = ({blob, open, onClose, onDownload}: PDFViewerProps) => {
  const [images, setImages] = useState<PDFPageImage[]>([]);

  useEffect(() => {
    const loadPDF = async () => {
      // It may seem strange to pass in a Blob and then ask it for an ArrayBuffer,
      // when we get an ArrayBuffer back from our API layer, but this is preventing
      // a "Cannot perform Construct on a detached ArrayBuffer" error in pdfjs.
      const pdf = await pdfjsLib.getDocument(await blob.arrayBuffer()).promise;
      const pageImages = [];

      for (let i = 1; i <= pdf.numPages; i++) {
        const page = await pdf.getPage(i);
        const viewport = page.getViewport({scale: 2});
        const canvas = document.createElement('canvas');
        const context = canvas.getContext('2d');
        if (!context) {
          console.error('getContext failed');
          return;
        }
        canvas.height = viewport.height;
        canvas.width = viewport.width;

        await page.render({canvasContext: context, viewport}).promise;

        pageImages.push({src: canvas.toDataURL()});
      }

      setImages(pageImages);
    };

    loadPDF();
  }, [blob]);

  const plugins = [Thumbnails];
  if (onDownload) {
    plugins.push(Download);
  }

  const download = onDownload
    ? {
        download: onDownload,
      }
    : undefined;

  return (
    <Lightbox
      open={open}
      close={onClose}
      slides={images}
      plugins={plugins}
      thumbnails={{
        position: 'start',
        vignette: true,
      }}
      carousel={{finite: true}}
      download={download}
    />
  );
};
