import {
  CallSchema,
  ObjectVersionSchema,
} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/wfDataModelHooksInterface';
import {useEffect, useRef} from 'react';

import {useOrgName} from '../../common/hooks/useOrganization';
import {useViewerUserInfo2} from '../../common/hooks/useViewerUserInfo';
import * as viewEvents from './viewEvents';

export const useViewTraceEvent = (call: CallSchema) => {
  const {loading: viewerLoading, userInfo} = useViewerUserInfo2();
  const {loading: orgNameLoading, orgName} = useOrgName({
    entityName: call.entity,
  });

  // This is a hack to avoid sending the same event multiple times
  // This is a temporary solution until we can figure out why the call page is being re-rendered so many times
  const eventSentRef = useRef('');

  useEffect(() => {
    if (
      !viewerLoading &&
      !orgNameLoading &&
      eventSentRef.current !== call.traceId
    ) {
      eventSentRef.current = call.traceId;
      if (call.spanName === 'Evaluation.evaluate') {
        viewEvents.evaluationViewed({
          traceId: call.traceId,
          userId: userInfo.id,
          organizationName: orgName,
          entityName: call.entity,
        });
      } else {
        viewEvents.traceViewed({
          traceId: call.traceId,
          userId: userInfo.id,
          organizationName: orgName,
          entityName: call.entity,
        });
      }
    }
  }, [viewerLoading, orgNameLoading, orgName, userInfo, call]);
};

export const useObjectViewEvent = (objectVersion: ObjectVersionSchema) => {
  const {loading: viewerLoading, userInfo} = useViewerUserInfo2();
  const {loading: orgNameLoading, orgName} = useOrgName({
    entityName: objectVersion.entity,
  });
  useEffect(() => {
    if (!viewerLoading && !orgNameLoading) {
      viewEvents.objectViewed({
        objectType: objectVersion.baseObjectClass ?? '',
        objectId: objectVersion.objectId,
        userId: userInfo.id,
        organizationName: orgName,
        entityName: objectVersion.entity,
      });
    }
  }, [viewerLoading, orgNameLoading, orgName, userInfo, objectVersion]);
};
