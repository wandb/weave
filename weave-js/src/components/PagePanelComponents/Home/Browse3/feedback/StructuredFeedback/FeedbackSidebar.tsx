import {toast} from '@wandb/weave/common/components/elements/Toast';
import {useOrgName} from '@wandb/weave/common/hooks/useOrganization';
import {useViewerInfo} from '@wandb/weave/common/hooks/useViewerInfo';
import {useViewerUserInfo2} from '@wandb/weave/common/hooks/useViewerUserInfo';
import {Button} from '@wandb/weave/components/Button';
import {Loading} from '@wandb/weave/components/Loading';
import {annotationsViewed} from '@wandb/weave/integrations/analytics/viewEvents';
import {makeRefCall} from '@wandb/weave/util/refs';
import React, {useEffect, useState} from 'react';
import {useHistory} from 'react-router-dom';

import {useWeaveflowRouteContext} from '../../context';
import {Empty} from '../../pages/common/Empty';
import {EMPTY_PROPS_ANNOTATIONS} from '../../pages/common/EmptyContent';
import {HumanAnnotationCell} from './HumanAnnotation';
import {tsHumanAnnotationSpec} from './humanAnnotationTypes';

type FeedbackSidebarProps = {
  humanAnnotationSpecs: tsHumanAnnotationSpec[];
  specsLoading: boolean;
  callID: string;
  entity: string;
  project: string;
};

export const FeedbackSidebar = ({
  humanAnnotationSpecs,
  specsLoading,
  callID,
  entity,
  project,
}: FeedbackSidebarProps) => {
  const history = useHistory();
  const router = useWeaveflowRouteContext().baseRouter;
  const [isSaving, setIsSaving] = useState(false);
  const [unsavedFeedbackChanges, setUnsavedFeedbackChanges] = useState<
    Record<string, () => Promise<boolean>>
  >({});

  const {loading: viewerLoading, userInfo} = useViewerUserInfo2();
  const {loading: orgNameLoading, orgName} = useOrgName({
    entityName: entity,
  });

  const save = async () => {
    setIsSaving(true);
    try {
      // Save all pending feedback changes
      const savePromises = Object.values(unsavedFeedbackChanges).map(saveFn =>
        saveFn()
      );
      const results = await Promise.all(savePromises);

      // Check if any saves failed
      if (results.some(result => !result)) {
        throw new Error('Not all feedback changes saved');
      }

      // Clear the unsaved changes after successful save
      setUnsavedFeedbackChanges({});
    } catch (error) {
      console.error('Error saving feedback:', error);
      toast(`Error saving feedback: ${error}`, {
        type: 'error',
      });
    } finally {
      setIsSaving(false);
    }
  };

  useEffect(() => {
    if (!viewerLoading && !orgNameLoading) {
      annotationsViewed({
        traceId: callID,
        userId: userInfo.id,
        organizationName: orgName,
        entityName: entity,
        projectName: project,
        numAnnotationSpecs: humanAnnotationSpecs.length,
      });
    }
  }, [
    viewerLoading,
    orgNameLoading,
    userInfo,
    orgName,
    entity,
    project,
    humanAnnotationSpecs.length,
    callID,
  ]);

  return (
    <div className="flex h-full w-full flex-col bg-white">
      <div className="justify-left flex w-full p-12">
        <div className="text-lg font-semibold">Feedback</div>
        <div className="flex-grow" />
      </div>
      <div className="min-h-1 mb-8 h-1 overflow-auto bg-moon-300" />
      {humanAnnotationSpecs.length > 0 ? (
        <>
          <div className="ml-6 h-full flex-grow overflow-auto">
            <HumanAnnotationInputs
              entity={entity}
              project={project}
              callID={callID}
              humanAnnotationSpecs={humanAnnotationSpecs.sort((a, b) =>
                (a.name ?? '').localeCompare(b.name ?? '')
              )}
              setUnsavedFeedbackChanges={setUnsavedFeedbackChanges}
            />
          </div>
          <div className="flex w-full border-t border-moon-300 p-12">
            <Button
              onClick={save}
              variant="primary"
              className="w-full"
              disabled={
                isSaving || Object.keys(unsavedFeedbackChanges).length === 0
              }
              size="large">
              {isSaving ? 'Saving...' : 'Save'}
            </Button>
          </div>
        </>
      ) : specsLoading ? (
        <div className="mt-12 w-full items-center justify-center">
          <Loading centered />
        </div>
      ) : (
        <div className="mr-10 mt-12 items-center justify-center">
          <Empty {...EMPTY_PROPS_ANNOTATIONS} />
          <div className="mt-4 flex w-full justify-center">
            <Button
              onClick={() =>
                history.push(router.scorersUIUrl(entity, project))
              }>
              View scorers
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};

type HumanAnnotationInputsProps = {
  entity: string;
  project: string;
  callID: string;
  humanAnnotationSpecs: tsHumanAnnotationSpec[];
  setUnsavedFeedbackChanges: React.Dispatch<
    React.SetStateAction<Record<string, () => Promise<boolean>>>
  >;
};

const HumanAnnotationInputs = ({
  entity,
  project,
  callID,
  humanAnnotationSpecs,
  setUnsavedFeedbackChanges,
}: HumanAnnotationInputsProps) => {
  const callRef = makeRefCall(entity, project, callID);
  const {loading: loadingUserInfo, userInfo} = useViewerInfo();

  if (loadingUserInfo) {
    return null;
  }
  const viewer = userInfo ? userInfo.id : null;

  return (
    <div>
      {humanAnnotationSpecs?.map((field, index) => (
        <div key={field.ref} className="px-16">
          <div className="bg-gray-50 text-md font-semibold">{field.name}</div>
          {field.description && (
            <div className="bg-gray-50 font-italic text-sm text-moon-700 ">
              {field.description}
            </div>
          )}
          <div className="pb-8 pt-4">
            <HumanAnnotationCell
              focused={index === 0}
              hfSpec={field}
              callRef={callRef}
              entity={entity}
              project={project}
              viewer={viewer}
              readOnly={false}
              setUnsavedFeedbackChanges={setUnsavedFeedbackChanges}
            />
          </div>
        </div>
      ))}
    </div>
  );
};
