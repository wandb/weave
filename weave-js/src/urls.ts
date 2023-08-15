export const URL_RECENT = 'recent';
export const URL_WANDB = 'wandb';
export const URL_LOCAL = 'local';

export function urlRecent(): string {
  return `/${URL_RECENT}/`;
}
export function urlRecentBoards(): string {
  return `${urlRecent()}board`;
}
export function urlRecentTables(): string {
  return `${urlRecent()}table`;
}

export function urlEntity(entityName: string): string {
  return `/${URL_WANDB}/${entityName}`;
}

export function urlProject(entityName: string, projectName: string): string {
  const encodedName = encodeURIComponent(projectName);
  return `${urlEntity(entityName)}/${encodedName}`;
}

export function urlProjectAssets(
  entityName: string,
  projectName: string,
  assetType: string
): string {
  return `${urlProject(entityName, projectName)}/${assetType}`;
}

export function urlProjectAssetPreview(
  entityName: string,
  projectName: string,
  assetType: string,
  preview: string
): string {
  const encodedPreview = encodeURIComponent(preview);
  return `${urlProjectAssets(
    entityName,
    projectName,
    assetType
  )}/${encodedPreview}`;
}

export function urlLocalBoards(): string {
  return `/${URL_LOCAL}/board/`;
}

export function urlLocalAssetPreview(preview: string): string {
  const encodedPreview = encodeURIComponent(preview);
  return `${urlLocalBoards()}${encodedPreview}`;
}
