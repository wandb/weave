import {useEffect, useMemo, useState} from 'react';

import {useWFHooks} from '../../pages/wfReactInterface/context';
import {objectVersionKeyToRefUri} from '../../pages/wfReactInterface/utilities';
import {ObjectVersionSchema} from '../../pages/wfReactInterface/wfDataModelHooksInterface';
import {
  HumanAnnotationPayload,
  tsHumanFeedbackColumn,
} from './humanFeedbackTypes';

export const useHumanFeedbackOptions = (
  entity: string,
  project: string
): tsHumanFeedbackColumn[] => {
  const {useRootObjectVersions} = useWFHooks();

  const [cols, setCols] = useState<ObjectVersionSchema[] | null>(null);
  const humanAnnotationColumns = useRootObjectVersions(
    entity,
    project,
    {
      baseObjectClasses: ['HumanAnnotationColumn'],
      latestOnly: true,
    },
    undefined, // limit
    false // metadataOnly
  );

  useEffect(() => {
    if (
      humanAnnotationColumns.loading ||
      humanAnnotationColumns.result == null
    ) {
      return;
    }
    setCols(humanAnnotationColumns.result);
  }, [humanAnnotationColumns.loading, humanAnnotationColumns.result]);

  return useMemo(() => {
    if (cols == null) {
      return [];
    }
    return cols.map(col => ({
      ...col.val,
      // attach object refs to the columns
      ref: objectVersionKeyToRefUri(col),
    }));
  }, [cols]);
};

export const extractValFromHumanAnnotationPayload = (
  payload: HumanAnnotationPayload
) => {
  if (payload.value == null) {
    return null;
  }
  const val = Object.values(Object.values(payload.value)[0])[0];
  return val;
};
