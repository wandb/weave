import _ from 'lodash';
import {useMemo} from 'react';

import {opNiceName} from '../common/Links';
import {useWFHooks} from '../wfReactInterface/context';
import {
  opVersionKeyToRefUri,
  refUriToObjectVersionKey,
  refUriToOpVersionKey,
} from '../wfReactInterface/utilities';
import {OpVersionSchema} from '../wfReactInterface/wfDataModelHooksInterface';

export const ALL_TRACES_OR_CALLS_REF_KEY = '__NO_REF__';
export const ANY_OP_GROUP_HEADER = '';
export const ALL_TRACES_TITLE = 'All Ops';
export const ALL_CALLS_TITLE = 'All Calls';
export const OP_GROUP_HEADER = 'Ops';
export const OP_VERSION_GROUP_HEADER = (currentOpId: string) =>
  `Specific Versions of ${opNiceName(currentOpId)}`;

export type WFHighLevelCallFilter = {
  traceRootsOnly?: boolean;
  opVersionRefs?: string[];
  inputObjectVersionRefs?: string[];
  outputObjectVersionRefs?: string[];
  parentId?: string | null;
  // This really doesn't belong here. We are using it to indicate that the
  // filter is frozen and should not be updated by the user. However, this
  // control should really be managed outside of the filter itself.
  frozen?: boolean;
};

/**
 * Given a frozen filter and an active filter, return the effective filter. The
 * effective filter is the combination of the two filters, with the frozen
 * filter taking precedence over the active filter. The effective filter is
 * guaranteed to be a valid filter with `traceRootsOnly` set correctly.
 */
export const getEffectiveFilter = (
  activeFilter: WFHighLevelCallFilter,
  frozenFilter?: WFHighLevelCallFilter
) => {
  const effectiveFilter = {
    ...activeFilter,
    ...(frozenFilter ?? {}),
  };

  // TraceRootsOnly is now only a calculated field
  effectiveFilter.traceRootsOnly =
    filterShouldUseTraceRootsOnly(effectiveFilter);

  validateFilterUICompatibility(effectiveFilter);
  return effectiveFilter;
};
/**
 * Given a filter, validate that it is a valid filter. If the filter is invalid,
 * an error will be thrown. Technically the backend can handle any combination
 * of filters, but the UI components are not setup to handle such cases. In the future
 * we should update the UI components to handle more complex filters and remove this.
 */
const validateFilterUICompatibility = (filter: WFHighLevelCallFilter) => {
  if ((filter.opVersionRefs?.length ?? 0) > 1) {
    throw new Error('Multiple op versions not yet supported');
  }

  if ((filter.inputObjectVersionRefs?.length ?? 0) > 1) {
    throw new Error('Multiple input object versions not yet supported');
  }

  if ((filter.outputObjectVersionRefs?.length ?? 0) > 1) {
    throw new Error('Multiple output object versions not yet supported');
  }
};

/**
 * Given a filter, return whether the filter should use trace roots only. A
 * filter should use trace roots only if the filter does not specify any
 * other fields.
 */
export const filterShouldUseTraceRootsOnly = (
  filter: WFHighLevelCallFilter
) => {
  const opVersionRefsSet = (filter.opVersionRefs?.length ?? 0) > 0;
  const inputObjectVersionRefsSet =
    (filter.inputObjectVersionRefs?.length ?? 0) > 0;
  const outputObjectVersionRefsSet =
    (filter.outputObjectVersionRefs?.length ?? 0) > 0;
  const parentIdSet = filter.parentId != null;
  return (
    !opVersionRefsSet &&
    !inputObjectVersionRefsSet &&
    !outputObjectVersionRefsSet &&
    !parentIdSet
  );
};
export const useInputObjectVersionOptions = (
  effectiveFilter: WFHighLevelCallFilter
) => {
  const {useObjectVersion} = useWFHooks();
  // We don't populate this one because it is expensive
  const currentRef = effectiveFilter.inputObjectVersionRefs?.[0] ?? null;
  const objectVersion = useObjectVersion(
    currentRef ? refUriToObjectVersionKey(currentRef) : null
  );
  return useMemo(() => {
    if (!currentRef || objectVersion.loading || !objectVersion.result) {
      return {};
    }
    return {
      [currentRef]: objectVersion.result,
    };
  }, [currentRef, objectVersion.loading, objectVersion.result]);
};
export const useOpVersionOptions = (
  entity: string,
  project: string,
  effectiveFilter: WFHighLevelCallFilter
): {
  [ref: string]: {
    title: string;
    ref: string;
    group: string;
    objectVersion?: OpVersionSchema;
  };
} => {
  const {useOpVersions} = useWFHooks();
  // Get all the "latest" versions
  const latestVersions = useOpVersions(entity, project, {
    latestOnly: true,
  });

  // Get all the versions of the currently selected op
  const currentRef = effectiveFilter.opVersionRefs?.[0] ?? null;
  const currentOpId = currentRef ? refUriToOpVersionKey(currentRef).opId : null;
  const currentVersions = useOpVersions(
    entity,
    project,
    {
      opIds: [currentOpId ?? ''],
    },
    undefined,
    {
      skip: !currentOpId,
    }
  );

  const opVersionOptionsWithoutAllSection = useMemo(() => {
    const result: Array<{
      title: string;
      ref: string;
      group: string;
      objectVersion?: OpVersionSchema;
    }> = [];

    _.sortBy(latestVersions.result ?? [], ov => [
      opNiceName(ov.opId).toLowerCase(),
      ov.opId.toLowerCase(),
    ]).forEach(ov => {
      const ref = opVersionKeyToRefUri({
        ...ov,
        versionHash: '*',
      });
      result.push({
        title: opNiceName(ov.opId),
        ref,
        group: OP_GROUP_HEADER,
      });
    });

    if (currentOpId) {
      _.sortBy(currentVersions.result ?? [], ov => -ov.versionIndex).forEach(
        ov => {
          const ref = opVersionKeyToRefUri(ov);
          result.push({
            title: opNiceName(ov.opId) + ':v' + ov.versionIndex,
            ref,
            group: OP_VERSION_GROUP_HEADER(currentOpId),
            objectVersion: ov,
          });
        }
      );
    }

    return _.fromPairs(result.map(r => [r.ref, r]));
  }, [currentOpId, currentVersions.result, latestVersions.result]);

  return useMemo(() => {
    return {
      [ALL_TRACES_OR_CALLS_REF_KEY]: {
        title: filterShouldUseTraceRootsOnly({
          ...effectiveFilter,
          opVersionRefs: [],
        })
          ? ALL_TRACES_TITLE
          : ALL_CALLS_TITLE,
        ref: '',
        group: ANY_OP_GROUP_HEADER,
      },
      ...opVersionOptionsWithoutAllSection,
    };
  }, [effectiveFilter, opVersionOptionsWithoutAllSection]);
};
export const useOutputObjectVersionOptions = (
  effectiveFilter: WFHighLevelCallFilter
) => {
  const {useObjectVersion} = useWFHooks();
  // We don't populate this one because it is expensive
  const currentRef = effectiveFilter.outputObjectVersionRefs?.[0] ?? null;
  const objectVersion = useObjectVersion(
    currentRef ? refUriToObjectVersionKey(currentRef) : null
  );
  return useMemo(() => {
    if (!currentRef || objectVersion.loading || !objectVersion.result) {
      return {};
    }
    return {
      [currentRef]: objectVersion.result,
    };
  }, [currentRef, objectVersion.loading, objectVersion.result]);
};
