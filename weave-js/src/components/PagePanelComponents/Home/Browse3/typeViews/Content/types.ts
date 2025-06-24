import {CustomWeaveTypePayload} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/typeViews/customWeaveType.types';

// type WithPrefix<T extends string> = `${T}${string}`;

export type ContentTypePayload = CustomWeaveTypePayload<
  'weave.type_wrappers.Content.content.Content',
  {content: string; 'metadata.json': string}
>;

export type ContentViewProps = {
  entity: string;
  project: string;
  mode?: string;
  data: ContentTypePayload;
};

export type ContentMetadata = {
  original_path?: string;
  size: number;
  filename: string;
  mimetype: string;
};

export type ContentViewMetadataLoadedProps = Omit<ContentViewProps, 'data'> & {
  metadata: ContentMetadata;
  content: string;
};

export type SizedContentViewMetadataLoadedProps =
  ContentViewMetadataLoadedProps & {
    width: number;
    height: number;
  };
