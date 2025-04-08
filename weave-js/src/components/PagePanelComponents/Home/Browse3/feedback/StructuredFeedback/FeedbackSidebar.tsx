import {toast} from '@wandb/weave/common/components/elements/Toast';
import {useOrgName} from '@wandb/weave/common/hooks/useOrganization';
import {useViewerInfo} from '@wandb/weave/common/hooks/useViewerInfo';
import {useViewerUserInfo2} from '@wandb/weave/common/hooks/useViewerUserInfo';
import {Button} from '@wandb/weave/components/Button';
import {Loading} from '@wandb/weave/components/Loading';
import {Tooltip} from '@wandb/weave/components/Tooltip';
import {annotationsViewed} from '@wandb/weave/integrations/analytics/viewEvents';
import {makeRefCall} from '@wandb/weave/util/refs';
import React, {useEffect, useState} from 'react';
import {useHistory} from 'react-router-dom';

import {Empty} from '../../pages/common/Empty';
import {EMPTY_PROPS_ANNOTATIONS} from '../../pages/common/EmptyContent';
import {CreateAnnotationFieldDrawer} from '../../pages/ScorersPage/CreateAnnotationFieldDrawer';
import {useWFHooks} from '../../pages/wfReactInterface/context';
import {useGetTraceServerClientContext} from '../../pages/wfReactInterface/traceServerClientContext';
import {useWeaveflowRouteContext} from '../../context';
import {HumanAnnotationCell} from './HumanAnnotation';
import {tsHumanAnnotationSpec} from './humanAnnotationTypes';

type FeedbackSidebarProps = {
  humanAnnotationSpecs: tsHumanAnnotationSpec[];
  specsLoading: boolean;
  callID: string;
  entity: string;
  project: string;
  onReloadSpecs?: () => void;
  onClose?: () => void;
};

export const FeedbackSidebar = ({
  humanAnnotationSpecs,
  specsLoading,
  callID,
  entity,
  project,
  onReloadSpecs,
  onClose,
}: FeedbackSidebarProps) => {
  const [isSaving, setIsSaving] = useState(false);
  const [isNewAnnotationDrawerOpen, setIsNewAnnotationDrawerOpen] = useState(false);
  const [unsavedFeedbackChanges, setUnsavedFeedbackChanges] = useState<
    Record<string, () => Promise<boolean>>
  >({});
  const {loading: viewerLoading, userInfo} = useViewerUserInfo2();
  const {loading: orgNameLoading, orgName} = useOrgName({
    entityName: entity,
  });
  const history = useHistory();
  const {baseRouter} = useWeaveflowRouteContext();

  const {useFeedback} = useWFHooks();
  const query = useFeedback({
    entity,
    project,
    weaveRef: callID,
  });

  const getTsClient = useGetTraceServerClientContext();
  useEffect(() => {
    return getTsClient().registerOnFeedbackListener(callID, query.refetch);
  }, [callID, query.refetch, getTsClient]);

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
      <div className="flex min-h-[32px] w-full items-center justify-between px-12">
        <div className="text-sm font-semibold">Annotation</div>
        <div className="flex items-center gap-2">
          <Tooltip 
            content="Manage annotation fields"
            trigger={
              <Button
                onClick={() => history.push(baseRouter.scorersUIUrl(entity, project))}
                variant="ghost"
                size="small"
                icon="settings"
                aria-label="Manage annotation fields"
              />
            }
          />
          {onClose && (
            <Button
              onClick={onClose}
              variant="ghost"
              size="small"
              icon="close"
              aria-label="Close feedback sidebar"
            />
          )}
        </div>
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
        <div className="flex flex-col items-center justify-center h-full">
          <div className="flex flex-col items-center mx-8 gap-16 mt-[38px]">
            <Empty {...EMPTY_PROPS_ANNOTATIONS} />
            <Button
              onClick={() => setIsNewAnnotationDrawerOpen(true)}
              variant="primary"
              icon="add-new">
              Add field
            </Button>
          </div>
          <CreateAnnotationFieldDrawer
            entity={entity}
            project={project}
            open={isNewAnnotationDrawerOpen}
            onClose={() => {
              setIsNewAnnotationDrawerOpen(false);
              query.refetch();
              onReloadSpecs?.();
            }}
            onSave={() => {
              query.refetch();
              onReloadSpecs?.();
            }}
          />
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
        <div key={field.ref} className="px-8">
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
