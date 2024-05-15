import _ from 'lodash';
import {useMemo} from 'react';

import {opNiceName} from '../common/Links';
import {useWFHooks} from '../wfReactInterface/context';
import {
  opVersionKeyToRefUri,
  refUriToOpVersionKey,
} from '../wfReactInterface/utilities';
import {OpVersionSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {
  filterShouldUseTraceRootsOnly,
  WFHighLevelCallFilter,
} from './callsTableFilter';

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
export const ALL_TRACES_OR_CALLS_REF_KEY = '__NO_REF__';
export const ANY_OP_GROUP_HEADER = '';
export const ALL_TRACES_TITLE = 'All Ops';
export const ALL_CALLS_TITLE = 'All Calls';
export const OP_GROUP_HEADER = 'Ops';
export const OP_VERSION_GROUP_HEADER = (currentOpId: string) =>
  `Specific Versions of ${opNiceName(currentOpId)}`;
