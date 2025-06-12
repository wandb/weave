import React, {useEffect, useRef} from 'react';

interface IframeImageProps {
  src: string;
  alt: string;
}

/**
 * This is the only way to render an image in a way that complelely ignores the filter applied
 * for night mode. CSS properties like filter are special and even ShadowDOM cannot escape them.
 */
export const IsolatedImage = ({src, alt}: IframeImageProps) => {
  const iframeRef = useRef<HTMLIFrameElement | null>(null);

  useEffect(() => {
    const iframe = iframeRef.current;

    if (!iframe) {
      return;
    }

    const iframeDoc = iframe.contentWindow?.document;
    if (iframeDoc) {
      try {
        iframeDoc.head.innerHTML = '';
        iframeDoc.body.innerHTML = '';
        iframeDoc.hasChildNodes();
        const img = iframeDoc.createElement('img');
        img.src = src;
        img.alt = alt;
        iframeDoc.body.appendChild(img);
        const styleElement = iframeDoc.createElement('style');
        styleElement.textContent = `
          html, body {
            margin: 0;
            padding: 0;
            overflow: hidden;
            width: 100%;
            height: 100%;
          }
          img {
            object-fit: contain;
            width: 100%;
            height: 100%;
          }
        `;
        iframeDoc.head.appendChild(styleElement);
      } catch (error) {
        console.error('Error writing to iframe document:', error);
      }
    }
  }, [src, alt]);

  return (
    <iframe
      ref={iframeRef}
      style={{
        width: '100%',
        height: '100%',
        border: 'none',
        display: 'block',
      }}
      title={alt}
      sandbox="allow-scripts allow-same-origin"></iframe>
  );
};
