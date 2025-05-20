/**
 * Show a filterable, sortable grid of model tiles.
 */
import React, {useEffect, useState} from 'react';

import {ExplorerLoaded} from './ExplorerLoaded';
import {MODEL_INFO} from './modelInfo';
import {InferenceContextType} from './types';

type ExplorerProps = {
  inferenceContext: InferenceContextType;
  collectionId?: string;
};

export const Explorer = ({collectionId, inferenceContext}: ExplorerProps) => {
  const containerRef = React.useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);

  useEffect(() => {
    if (!containerRef.current) return;

    const resizeObserver = new ResizeObserver(entries => {
      for (const entry of entries) {
        setWidth(entry.contentRect.width);
      }
    });

    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
    };
  }, []);

  return (
    <div ref={containerRef} className="h-full w-full">
      <ExplorerLoaded
        modelInfo={MODEL_INFO}
        collectionId={collectionId}
        width={width}
        inferenceContext={inferenceContext}
      />
    </div>
  );
};
