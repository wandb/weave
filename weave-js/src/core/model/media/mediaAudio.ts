export interface WBAudio {
  type: 'audio-file';
  digest: string;
  path: string;
  sample_rate: number;
  caption: string | null;
}
