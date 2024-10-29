import {useEffect, useMemo, useState} from 'react';

import {useWFHooks} from '../../pages/wfReactInterface/context';
import {objectVersionKeyToRefUri} from '../../pages/wfReactInterface/utilities';
import {ObjectVersionSchema} from '../../pages/wfReactInterface/wfDataModelHooksInterface';
import {tsHumanFeedbackSpec} from './humanFeedbackTypes';


const useResolveTypeObjects = (typeRefs: string[]) => {
  const {useRefsData} = useWFHooks();
  const refsData = useRefsData(typeRefs);
  return useMemo(() => {
    if (refsData.loading || refsData.result == null) {
      return null;
    }
    const refDataWithRefs = refsData.result.map((x, i) => ({
      ...x,
      ref: typeRefs[i],
    }));
    return refDataWithRefs;
  }, [refsData.loading, refsData.result]);
};


export const useHumanFeedbackOptions = (
  entity: string,
  project: string
): tsHumanFeedbackSpec | null => {
  const {useRootObjectVersions} = useWFHooks();

  const [latestSpec, setLatestSpec] = useState<ObjectVersionSchema | null>(
    null
  );
  const humanFeedbackObjects = useRootObjectVersions(
    entity,
    project,
    {
      baseObjectClasses: ['HumanFeedback'],
      latestOnly: true,
    },
    undefined, // limit
    false // metadataOnly
  );
  // TODO: this is not actually tsHumanFeedbackSpec, it's HumanFeedbackSpec
  // we need to add the refs for each of the feedback fields
  const feedbackFieldRefs = latestSpec?.val?.feedback_fields ?? []
  const feedbackFields = useResolveTypeObjects(feedbackFieldRefs);

  console.log('feedbackFields', feedbackFields);

  useEffect(() => {
    if (humanFeedbackObjects.loading || humanFeedbackObjects.result == null) {
      return;
    }
    // sort by createdAtMs, most recent first
    const spec = humanFeedbackObjects.result
      ?.sort((a, b) => b.createdAtMs - a.createdAtMs)
      .pop();
    if (!spec) {
      return;
    }
    setLatestSpec(spec);
  }, [humanFeedbackObjects.loading, humanFeedbackObjects.result]);

  return useMemo(() => {
    if (latestSpec == null || feedbackFields == null) {
      return null;
    }
    return {
      feedback_fields: feedbackFields,
      ref: objectVersionKeyToRefUri(latestSpec),
    };
  }, [latestSpec, feedbackFields]);
};
