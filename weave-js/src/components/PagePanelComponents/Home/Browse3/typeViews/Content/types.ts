import {CustomWeaveTypePayload} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/typeViews/customWeaveType.types';


type WithPrefix<T extends string> = `${T}${string}`;

type StartsWithPrefix = WithPrefix<'prefix'>;
type UnionExample = WithPrefix<'abc' | 'def'>;

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

export type ContentViewMetadataLoadedProps = ContentViewProps & {
  metadata: ContentMetadata;
  content: string;
};

