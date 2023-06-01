// TODO: this type needs some love
export interface File {
  id: string;
  name: string;
  url?: string | null;
  sizeBytes: number;
  // Run files always passes updatedAt, ArtifactFiles never does (individual
  // file timestamps aren't very useful for artifacts)
  updatedAt?: Date | null;

  // ArtifactFiles may pass either of these, or both
  ref?: string;
  digest?: string;
  selected?: boolean;
  disabled?: boolean;
  artifact?: {
    id: string;
    digest: string;
  } | null;
  storagePolicyConfig?: {
    storageRegion?: string;
    storageLayout?: string;
  };
}
