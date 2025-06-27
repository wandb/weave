import {parseRefMaybe} from '@wandb/weave/react';
import {useMemo} from 'react';

import {ObjectVersionSchema} from '../../components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/wfDataModelHooksInterface';

export type StorageSizeResult = {
  currentVersionSizeBytes?: number;
  allVersionsSizeBytes?: number;
  shouldShowAllVersions: boolean;
  isLoading: boolean;
};

/**
 * Calculate storage size for dataset versions
 */
export function useDatasetStorageSizeCalculation(
  objectVersions: {loading: boolean; result?: ObjectVersionSchema[] | null},
  objectVersionIndex: number,
  tableStats: {
    loading: boolean;
    result?: {
      tables: Array<{
        digest: string;
        storage_size_bytes: number;
      }>;
    } | null;
  }
): StorageSizeResult {
  return useMemo(() => {
    // Track the loading state
    const isLoading = objectVersions.loading || tableStats.loading;

    // Return early with consistent undefined values if data is not available
    if (
      !objectVersions.result ||
      !tableStats.result ||
      !tableStats.result.tables
    ) {
      return {
        currentVersionSizeBytes: undefined,
        allVersionsSizeBytes: undefined,
        shouldShowAllVersions: false,
        isLoading,
      };
    }

    // Build a map of table digests to their storage sizes
    const tableSizeMap = new Map(
      tableStats.result.tables.map(r => [r.digest, r.storage_size_bytes])
    );

    // Calculate size for each version
    const versionSizeMap = new Map(
      objectVersions.result.map(({versionIndex, sizeBytes, val}) => {
        const metadataSizeBytes = sizeBytes ?? 0;
        const ref = parseRefMaybe(val.rows);

        const tableDataSizeBytes =
          tableSizeMap.get(ref?.artifactVersion ?? '') ?? 0;

        return [versionIndex, metadataSizeBytes + tableDataSizeBytes];
      })
    );

    const currentVersionSizeBytes = versionSizeMap.get(objectVersionIndex);

    // Calculate total size directly during iteration to avoid creating additional arrays
    let totalSize = 0;
    versionSizeMap.forEach(size => {
      totalSize += size;
    });

    return {
      currentVersionSizeBytes,
      allVersionsSizeBytes: totalSize,
      shouldShowAllVersions: objectVersions.result.length > 1,
      isLoading,
    };
  }, [objectVersions, objectVersionIndex, tableStats]);
}

/**
 * Calculate storage size for regular object versions
 */
export function useObjectStorageSizeCalculation(
  objectVersions: {loading: boolean; result?: ObjectVersionSchema[] | null},
  objectVersionIndex: number
): StorageSizeResult {
  return useMemo(() => {
    // Track loading state
    const isLoading = objectVersions.loading;

    // Return early with consistent undefined values if data is not available
    if (!objectVersions.result) {
      return {
        currentVersionSizeBytes: undefined,
        allVersionsSizeBytes: undefined,
        shouldShowAllVersions: false,
        isLoading,
      };
    }

    const currentVersion = objectVersions.result.find(
      v => v.versionIndex === objectVersionIndex
    );

    // Calculate total size directly in the loop to avoid unnecessary array operations
    let totalSize = 0;
    for (const version of objectVersions.result) {
      totalSize += version.sizeBytes ?? 0;
    }

    return {
      currentVersionSizeBytes: currentVersion?.sizeBytes,
      allVersionsSizeBytes: totalSize,
      shouldShowAllVersions: objectVersions.result.length > 1,
      isLoading,
    };
  }, [objectVersions, objectVersionIndex]);
}
