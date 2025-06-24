import React from 'react';

import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import {useWFHooks} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/context';
import {ContentMetadata, ContentViewProps} from './types';
import {ImageContent} from './ImageView';
import {AudioContent} from './AudioView';
import { PDFContent } from './PDFView';
import { VideoContent } from './VideoView';

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

  if (metadataJson.mimetype.startsWith('image')) {
    return (
      <ImageContent
        entity={entity}
        project={project}
        metadata={metadataJson}
        content={content}
      />
    )
  }
  else if (metadataJson.mimetype.startsWith('audio')) {
    return (
      <AudioContent
        entity={entity}
        project={project}
        metadata={metadataJson}
        content={content}
      />
    )
  }
  else if (metadataJson.mimetype.startsWith('video')) {
    return (
      <VideoContent
        entity={entity}
        project={project}
        metadata={metadataJson}
        content={content}
      />
    )
  }
  else if (metadataJson.mimetype === ('application/pdf')) {
    return (
      <PDFContent
        entity={entity}
        project={project}
        metadata={metadataJson}
        content={content}
      />
    )
  }
  return (
    <div>
      Fallback
    </div>
  )
  //   <ContentViewMetadataLoaded
  //     data={data}
  //     entity={entity}
  //     project={project}
  //     metadata={metadataJson}
  //     content={content}
  //   />
  // );
};
