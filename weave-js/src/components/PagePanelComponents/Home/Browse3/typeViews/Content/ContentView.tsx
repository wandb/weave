import React, {useCallback, useEffect, useState} from 'react';

import {Icon} from '@wandb/weave/components/Icon';
import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import {useWFHooks} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/context';
import {CustomWeaveTypePayload} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/typeViews/customWeaveType.types';
import {getContentHandler} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/typeViews/Content/Handlers/ContentHandler';
import {getIconName} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/typeViews/Content/Handlers/Shared';
import { AutoSizer } from 'react-virtualized';

// Save a Blob as a content in the user's downloads folder in a
// cross-browser compatible way.
const saveBlob = (blob: Blob, filename: string) => {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  });
};

type ContentTypePayload = CustomWeaveTypePayload<
  'weave.type_wrappers.Content.content.Content',
  {content: string; 'metadata.json': string}
>;

type ContentViewProps = {
  entity: string;
  project: string;
  mode?: string;
  data: ContentTypePayload;
};

type ContentMetadata = {
  original_path?: string;
  mimetype: string;
  size: number;
  filename: string;
};

export const ContentView = ({entity, project, data}: ContentViewProps) => {
  const {useFileContent} = useWFHooks();
  const metadata = useFileContent({
    entity,
    project,
    digest: data.files['metadata.json'],
  });

  if (metadata.loading) {
    return <LoadingDots />;
  }
  // TODO: Should add an explicit error condition to useFileContent
  if (metadata.result == null) {
    return <span>Metadata not found</span>;
  }

  // Convert ArrayBuffer to JSON
  let metadataJson: ContentMetadata;
  try {
    const decoder = new TextDecoder();
    const jsonString = decoder.decode(metadata.result);
    metadataJson = JSON.parse(jsonString);
  } catch (error) {
    console.error('Error parsing metadata JSON:', error);
    return <span>Error parsing metadata</span>;
  }

  const content = data.files['content'];

  return (
    <AutoSizer style={{height: '100%', width: '100%'}}>
      {({width, height}) => {
        if (width === 0 || height === 0) {
          return null;
        }
        return (
          <ContentViewMetadataLoaded
            entity={entity}
            project={project}
            metadata={metadataJson}
            content={content}
            containerWidth={width}
            containerHeight={height}
          />
        );
      }}
    </AutoSizer>
  );
};

type ContentViewMetadataLoadedProps = {
  entity: string;
  project: string;
  metadata: ContentMetadata;
  content: string;
  containerWidth: number;
  containerHeight: number;
};

const ContentViewMetadataLoaded = ({
  entity,
  project,
  metadata,
  content,
  containerWidth,
  containerHeight
}: ContentViewMetadataLoadedProps) => {
  const [contentResult, setContentResult] = useState<Blob | null>(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [videoPlaybackStates, setVideoPlaybackStates] = useState<
    Record<string, {currentTime: number; volume: number; muted: boolean}>
  >({});
  const {useFileContent} = useWFHooks();
  const {filename, size, mimetype} = metadata;
  const contentContent = useFileContent({
    entity,
    project,
    digest: content,
    skip: !isDownloading,
  });

  // Store the last non-null content content result in state
  // We do this because passing skip: true to useFileContent will
  // result in contentContent.result getting returned as null even
  // if it was previously downloaded successfully.
  useEffect(() => {
    if (contentContent.result) {
      const blob = new Blob([contentContent.result], {
        type: mimetype,
      });

      setContentResult(blob);
      setIsDownloading(false);
    }
  }, [contentContent.result, mimetype]);

  const doSave = useCallback(() => {
    if (!contentResult) {
      console.error('No content result');
      return;
    }
    saveBlob(contentResult, filename);
  }, [contentResult, filename]);

  const downloadContent = () => {
    if (!contentResult && !isDownloading) {
      setIsDownloading(true);
    } else if (contentResult) {
      // We really want to know if we are duplicating these large downloads
      console.warn('Attempted to download previously loaded content.');
    }
  };

  const openPreview = () => {
    setShowPreview(true);
    if (!contentResult && !isDownloading) {
      downloadContent();
    }
  };
  const closePreview = () => {
    setShowPreview(false);
  };

  const updateVideoPlaybackState = useCallback(
    (
      videoId: string,
      newState: Partial<{currentTime: number; volume: number; muted: boolean}>
    ) => {
      setVideoPlaybackStates(prev => ({
        ...prev,
        [videoId]: {
          ...(prev[videoId] || {currentTime: 0, volume: 1, muted: false}), // Default initial state
          ...newState,
        },
      }));
    },
    []
  );

  const iconStart = <Icon name={getIconName(mimetype)} />;

  const handlerProps = {
    mimetype,
    filename,
    size,
    containerHeight,
    containerWidth,
    iconStart,
    showPreview,
    isDownloading,
    contentResult,
    openPreview,
    closePreview,
    doSave,
    setShowPreview,
    setIsDownloading,
    videoPlaybackState: videoPlaybackStates[content],
    updateVideoPlaybackState: (
      newState: Partial<{currentTime: number; volume: number; muted: boolean}>
    ) => updateVideoPlaybackState(content, newState),
  };

  return getContentHandler(handlerProps);
};
