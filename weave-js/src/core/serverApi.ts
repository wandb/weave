import * as Vega3 from './_external/util/vega3';
import type {
  ArtifactFileContent,
  ArtifactFileDirectUrl,
  DirMetadata,
  FileMetadata,
  RunFileContent,
} from './model/types';

export interface ServerAPI {
  execute(query: Vega3.Query): Promise<any>;

  resetExecutionCache(): Promise<void>;

  getArtifactFileContents(
    artifactId: string,
    assetPath: string
  ): Promise<ArtifactFileContent>;

  getArtifactFileDirectUrl(
    artifactId: string,
    assetPath: string
  ): Promise<ArtifactFileDirectUrl>;

  getArtifactFileMetadata(
    artifactId: string,
    assetPath: string
  ): Promise<DirMetadata | FileMetadata | null>;

  getRunFileContents(
    projectName: string,
    runName: string,
    fileName: string,
    entityName?: string
  ): Promise<RunFileContent>;
}
