import React, {useCallback, useEffect, useState} from 'react';

import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import {useWFHooks} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/context';
import {ContentMetadata, ContentViewProps, ContentViewMetadataLoadedProps} from './types';
import {ImageContent} from './ImageView';
import {AudioContent} from './AudioView';
import { PDFContent } from './PDFView';
import { VideoContent } from './VideoView';
import {TailwindContents} from '@wandb/weave/components/Tailwind';
import {ContentMetadataTooltip, ContentTooltipWrapper, DownloadButton, getIconName, IconWithText, saveBlob} from './Shared';

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
      <IconWithText
        iconName={iconName}
        filename={filename}
      />
    </div>
  );

  const tooltipTrigger = (
    <ContentTooltipWrapper
      showPreview={false}
      tooltipHint="Click button to download"
      body={iconWithText}
    >
      <ContentMetadataTooltip
        filename={filename}
        mimetype={mimetype}
        size={size}
      />
    </ContentTooltipWrapper>
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
    )
  }
  else if (metadataJson.mimetype.startsWith('audio')) {
    contentView = (
      <AudioContent
        entity={entity}
        project={project}
        metadata={metadataJson}
        content={content}
      />
    )
  }
  else if (metadataJson.mimetype.startsWith('video')) {
    contentView = (
      <VideoContent
        entity={entity}
        project={project}
        metadata={metadataJson}
        content={content}
      />
    );
  }
  else if (metadataJson.mimetype === ('application/pdf')) {
    contentView = (
      <PDFContent
        entity={entity}
        project={project}
        metadata={metadataJson}
        content={content}
      />
    );
  }
  else {
    contentView = (
      <FallbackContent
        entity={entity}
        project={project}
        metadata={metadataJson}
        content={content}
      />
    )
  }
  return contentView;
};
