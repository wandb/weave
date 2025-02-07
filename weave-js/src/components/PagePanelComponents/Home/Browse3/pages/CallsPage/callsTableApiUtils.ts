import {FlattenedCallData} from './CallsTable';

function isApiRefLoaded(api: any): boolean {
  return Boolean(api && typeof api.getAllRowIds === 'function');
}

export function getAllRowIds(
  api: any,
  fallback: FlattenedCallData[]
): string[] {
  return isApiRefLoaded(api) ? api.getAllRowIds() : fallback.map(r => r.id);
}

export function getSelectedRowIds(
  api: any,
  fallback: FlattenedCallData[]
): string[] {
  return isApiRefLoaded(api)
    ? api.getAllRowIds().filter((id: string) => api.getRow(id)?.isSelected)
    : fallback.filter(r => r.isSelected).map(r => r.id);
}

export function updateRows(api: any, updates: any[]): void {
  if (isApiRefLoaded(api)) {
    api.updateRows(updates);
  }
}

export function clearSelectedCalls(api: any, rows: FlattenedCallData[]): void {
  const allRowIds = getAllRowIds(api, rows);
  updateRows(
    api,
    allRowIds.map(id => ({id, isSelected: false}))
  );
}

export function getRow(api: any, id: string): FlattenedCallData | undefined {
  return isApiRefLoaded(api) ? api.getRow(id) : undefined;
}
