import {StyledTooltip} from '@wandb/weave/components/DraggablePopups';
import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import {useWFHooks} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/context';
import {TailwindContents} from '@wandb/weave/components/Tailwind';
import React, {useCallback, useEffect, useState} from 'react';

import {AudioContent} from './AudioView';
import {ImageContent} from './ImageView';
import {PDFContent} from './PDFView';
import {
  ContentMetadataTooltip,
  DownloadButton,
  getIconName,
  IconWithText,
  saveBlob,
} from './Shared';
import {
  ContentMetadata,
  ContentViewMetadataLoadedProps,
  ContentViewProps,
} from './types';
import {VideoContent} from './VideoView';

const FallbackContent = (props: ContentViewMetadataLoadedProps) => {
  const [contentResult, setContentResult] = useState<Blob | null>(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const {useFileContent} = useWFHooks();
  const {metadata, project, entity, content} = props;
  const {filename, size, mimetype} = metadata;

  const contentContent = useFileContent({
    entity,
    project,
    digest: content,
    skip: !isDownloading,
  });

  // Store the last non-null content content result in state
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
      if (!isDownloading) {
        setIsDownloading(true);
      }
      return;
    }
    saveBlob(contentResult, filename);
  }, [contentResult, filename, isDownloading]);

  const iconName = getIconName(mimetype);

  const iconWithText = (
    <div>
      <IconWithText iconName={iconName} filename={filename} />
    </div>
  );

  const tooltipTrigger = (
    <StyledTooltip
      enterDelay={500}
      title={
        <TailwindContents>
          <ContentMetadataTooltip
            filename={filename}
            mimetype={mimetype}
            size={size}
          />
          <div className="text-sm">
            <div className="mt-8 text-center text-xs">
              Click button to download
            </div>
          </div>
        </TailwindContents>
      }>
      {iconWithText}
    </StyledTooltip>
  );

  return (
    <TailwindContents>
      <div className="group flex items-center gap-4">
        {tooltipTrigger}
        <div className="opacity-0 group-hover:opacity-100">
          <DownloadButton isDownloading={isDownloading} doSave={doSave} />
        </div>
      </div>
    </TailwindContents>
  );
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
  let contentView;

  if (metadataJson.mimetype.startsWith('image')) {
    contentView = (
      <ImageContent
        entity={entity}
        project={project}
        metadata={metadataJson}
        content={content}
      />
    );
  } else if (metadataJson.mimetype.startsWith('audio')) {
    contentView = (
      <AudioContent
        entity={entity}
        project={project}
        metadata={metadataJson}
        content={content}
      />
    );
  } else if (metadataJson.mimetype.startsWith('video')) {
    contentView = (
      <VideoContent
        entity={entity}
        project={project}
        metadata={metadataJson}
        content={content}
      />
    );
  } else if (metadataJson.mimetype === 'application/pdf') {
    contentView = (
      <PDFContent
        entity={entity}
        project={project}
        metadata={metadataJson}
        content={content}
      />
    );
  } else {
    contentView = (
      <FallbackContent
        entity={entity}
        project={project}
        metadata={metadataJson}
        content={content}
      />
    );
  }
  return contentView;
};
