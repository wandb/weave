import * as _ from 'lodash';
// images from a single history data point
export interface ImageMetadata {
  width: number;
  height: number;
  count: number; // number of images
  _type: 'image-file' | 'images' | 'images/separated';
  caption?: string;
  captions: string[]; // one caption per image
  format?: string;
  path?: string;
  artifact_path?: string;
  grouping?: number; // if grouping is set to N, we'll group images in batches of N in the UI.  (Example use case: uploaded images are input, output, and expected)
  masks?: ManyMasks;
  boxes?: ManyBoxes;
  all_masks?: ManyMasks[];
  all_boxes?: ManyBoxes[];
}

export type LayoutType = 'ALL_STACKED' | 'MASKS_NEXT_TO_IMAGE' | 'ALL_SPLIT';

export interface ManyMasks {
  [key: string]: WBFile;
}

export interface ManyBoxes {
  [key: string]: WBFile;
}

export interface BoundingBoxFileData {
  box_data: BoundingBox2D[];
  class_labels: {[key: number]: string};
}

// TODO MOVE
interface WBFile {
  path: string;
  _type: string;
  sha256: string;
  size: 144;
}

export interface Mask {
  mask_data: WBFile;
  class_labels: {
    [key: string]: string;
  };
}

interface PositionMiddleBase {
  middle: [number, number];
  width: number;
  height: number;
}

interface PositionMinMax {
  minX: number;
  maxX: number;
  minY: number;
  maxY: number;
}

export const returnIfBoundingBox3D = (
  bbox: BoundingBox2D | BoundingBox3D
): BoundingBox3D | undefined =>
  'type' in bbox && bbox.type === '3d' ? bbox : undefined;

export const returnIfBoundingBox2D = (
  bbox: BoundingBox2D | BoundingBox3D
): BoundingBox2D | undefined => (!('type' in bbox) ? bbox : undefined);

export interface BoundingBox2D {
  position: PositionMiddleBase | PositionMinMax;
  class_id: number;
  box_caption?: string;
  scores?: {
    [key: string]: number;
  };
  domain?: 'pixel';
}
export interface BoundingBox3D {
  type: '3d';
  classInfo?: {label: string; id: number};
  score?: number;
}

// audio from a single history data point
export interface AudioMetadata {
  _type: 'audio';
  count: number; // number of audio files
  sampleRates: number[];
  durations: number[];
  captions?: string[];
}

export type TableCellValue = unknown;

export interface TableMetadata {
  _type: 'table';
  columns: Array<string | number | boolean>; // the column headers for the table
  data?: Array<TableCellValue | TableCellValue[]>; // the text for the table
}
export function isTableMetadata(v: any): v is TableMetadata {
  return v?._type === 'table' && _.isArray(v.columns);
}

export interface HtmlMetadata {
  _type: 'html';
  count: number; // number of html files
}

export interface MediaCardMetadata {
  width: number | null;
  height: number | null;
  grouping?: number;
  sizingSettings: any; // TODO(p0): type
  count?: number;
}

/*
 * A bunch of the original media strings ("images", "audio", "html", "object3D")
 * actually represent arrays of their respective types. We made the
 * unfortunately-named "image-file", "audio-file", and "html-file" later for
 * individual objects.
 */
export type MediaString =
  | 'data-frame'
  | 'table'
  | 'table-file'
  | 'images'
  | 'images/separated'
  | 'image-file'
  | 'videos'
  | 'video-file'
  | 'audio'
  | 'audio-file'
  | 'html'
  | 'html-file'
  | 'plotly'
  | 'plotly-file'
  | 'object3D'
  | 'object3D-file'
  | 'bokeh'
  | 'bokeh-file'
  | 'molecule'
  | 'molecule-file'
  | 'media'; // media is used for MessageMediaNotFound

export const mediaStrings = [
  'table',
  'table-file',
  'partitioned-table',
  'joined-table',
  'images',
  'images/separated',
  'image-file',
  'videos',
  'video-file',
  'audio',
  'audio-file',
  'html',
  'html-file',
  'object3D',
  'object3D-file',
  'bokeh',
  'bokeh-file',
  'molecule',
  'molecule-file',
  'plotly',
  'plotly-file',
  'data-frame',
] as MediaString[];

// The subset of types supported by the media panels
// The other types use the media code path for uploaded
// file and associated by runs, but they are rendered by
// other Panels, not the media panel
export type MediaCardString =
  | 'table'
  | 'table-file'
  | 'images'
  | 'images/separated'
  | 'image-file'
  | 'videos'
  | 'video-file'
  | 'audio'
  | 'audio-file'
  | 'html'
  | 'html-file'
  | 'plotly'
  | 'plotly-file'
  | 'object3D'
  | 'object3D-file'
  | 'bokeh'
  | 'bokeh-file'
  | 'molecule'
  | 'molecule-file';

// A simplified version of the media types
// This is useful for logic around different media types
// without dealing with all of the different key names
export type MediaCardType =
  | 'image'
  | 'video'
  | 'object3D'
  | 'bokeh'
  | 'molecule'
  | 'table'
  | 'html'
  | 'audio'
  | 'plotly';

export const mediaCardStrings = [
  'image',
  'video',
  'object3D',
  'molecule',
  'table',
  'html',
  'bokeh',
  'audio',
  'plotly',
] as MediaCardType[];

export const isMediaCardType = (type: string) => {
  return _.includes(mediaCardStrings, type);
};

export const mediaCardTypeToKeys = (mediaType: MediaCardType) => {
  const mapping: {[k in MediaCardType]: MediaCardString[]} = {
    image: ['images', 'image-file', 'images/separated'],
    audio: ['audio-file', 'audio'],
    video: ['videos', 'video-file'],
    object3D: ['object3D-file', 'object3D'],
    bokeh: ['bokeh-file', 'bokeh'],
    table: ['table', 'table-file'],
    plotly: ['plotly', 'plotly-file'],
    html: ['html', 'html-file'],
    molecule: ['molecule', 'molecule-file'],
  };

  return mapping[mediaType] as MediaCardString[];
};

export function keyToMediaCardType(mediaType: MediaCardString): MediaCardType {
  const mapping: {[k in MediaCardString]: MediaCardType} = {
    'image-file': 'image',
    images: 'image',
    'images/separated': 'image',
    'audio-file': 'audio',
    audio: 'audio',
    'video-file': 'video',
    videos: 'video',
    object3D: 'object3D',
    'object3D-file': 'object3D',
    bokeh: 'bokeh',
    'bokeh-file': 'bokeh',
    molecule: 'molecule',
    'molecule-file': 'molecule',
    table: 'table',
    'table-file': 'table',
    plotly: 'plotly',
    'plotly-file': 'plotly',
    html: 'html',
    'html-file': 'html',
  };

  return mapping[mediaType];
}

export interface MaskOptions {
  maskKeys: string[];
  showImage?: boolean;
}
