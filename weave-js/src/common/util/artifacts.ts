export interface ArtifactLabels {
  [key: string]: string[];
}

export interface Label {
  key: string;
  val: string;
}

export function parseArtifactTypeDescription(desc?: string) {
  if (desc == null) {
    return {description: '', schema: undefined};
  }
  const lines = desc.split('\n');
  if (lines.length === 0) {
    return {description: '', schema: undefined};
  } else if (lines.length === 1) {
    return {description: lines[0], schema: undefined};
  }
  return {description: lines[0], schema: lines.slice(1).join('\n')};
}

export function createArtifactTypeDescription(
  description: string,
  schema?: string
) {
  const firstDescriptionLine = description.split('\n')[0];
  if (schema == null) {
    return firstDescriptionLine;
  }
  return [firstDescriptionLine, schema].join('\n');
}

export function parseArtifactLabels(tagsString: string): ArtifactLabels {
  try {
    return JSON.parse(tagsString);
  } catch {
    //
  }
  return {};
}

export function parseLabelString(labelString: string): Label {
  const [key, val] = labelString.split(':');
  return {
    key: key || '',
    val: val || '',
  };
}

export function newLabelValid(label: Label) {
  return label.key.length > 2 && label.val.length > 0;
}

export function newAliasValid(alias: string) {
  return alias.length > 0;
}

export function artifactNiceName(
  artifact: {
    digest: string;
    commitHash?: string | null;
    versionIndex?: number | null;
    artifactSequence: {
      name: string;
    };
  },
  opts?: {
    shortenDigest?: boolean;
  }
): string {
  if (artifact.versionIndex != null) {
    return `${artifact.artifactSequence.name}:v${artifact.versionIndex}`;
  }

  let digest = artifact.commitHash || artifact.digest;
  if (opts?.shortenDigest) {
    digest = digest.slice(0, 6);
  }
  return `${artifact.artifactSequence.name}:${digest}`;
}

export function artifactMembershipNiceName(
  collectionName: string,
  identifier: {versionIndex: number} | {digest: string} | {commitHash: string}
): string {
  let alias = '';
  if ('versionIndex' in identifier) {
    alias = `v${identifier.versionIndex}`;
  } else if ('commitHash' in identifier) {
    alias = identifier.commitHash;
  } else {
    alias = identifier.digest;
  }
  return `${collectionName}:${alias}`;
}

export function isVersionAlias(alias: {alias: string}): boolean {
  const versionRegex: RegExp = /^v(\d+)$/;
  return versionRegex.test(alias.alias);
}

export function getDescriptionSummary(artifactDescription: string) {
  return artifactDescription.split('\n')[0];
}
