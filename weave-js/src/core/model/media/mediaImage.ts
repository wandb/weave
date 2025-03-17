import {BoundingBox2D} from '../../_external/types/media';

interface MaskFile {
  type: 'mask-file';
  digest: string;
  path: string;
}

interface ClassesFile {
  type: 'classes-file';
  digest: string;
  path: string;
}

export interface WBImage {
  type: 'image-file';
  digest: string;
  path: string;
  width: number;
  height: number;
  boxes?: {
    [boxGroup: string]: BoundingBox2D[];
  };
  masks?: {
    [maskName: string]: MaskFile;
  };
  classes?: ClassesFile;
}

export interface ClassSet {
  type: 'class-set';
  class_set: Array<{name: string; id: number; color: string}>;
}
