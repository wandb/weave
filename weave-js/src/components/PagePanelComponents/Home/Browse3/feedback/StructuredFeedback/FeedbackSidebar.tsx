import {toast} from '@wandb/weave/common/components/elements/Toast';
import {useViewerInfo} from '@wandb/weave/common/hooks/useViewerInfo';
import {Button} from '@wandb/weave/components/Button';
import {Icon} from '@wandb/weave/components/Icon';
import {makeRefCall} from '@wandb/weave/util/refs';
import React, {useState} from 'react';
import {useHistory} from 'react-router-dom';

import {useWeaveflowRouteContext} from '../../context';
import {Empty} from '../../pages/common/Empty';
import {EMPTY_PROPS_ANNOTATIONS} from '../../pages/common/EmptyContent';
import {HumanAnnotationCell} from './HumanAnnotation';
import {tsHumanAnnotationSpec} from './humanAnnotationTypes';

type FeedbackSidebarProps = {
  humanAnnotationSpecs: tsHumanAnnotationSpec[];
  callID: string;
  entity: string;
  project: string;
};

export const FeedbackSidebar = ({
  humanAnnotationSpecs,
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

  return (
    <div className="flex h-full flex-col bg-white">
      <div className="justify-left flex w-full border-b border-moon-300 p-12">
        <div className="text-lg font-semibold">Feedback</div>
        <div className="flex-grow" />
      </div>
      {humanAnnotationSpecs.length > 0 ? (
        <>
          <div className="mx-6 h-full flex-grow overflow-auto">
            <HumanAnnotationSection
              entity={entity}
              project={project}
              callID={callID}
              humanAnnotationSpecs={humanAnnotationSpecs}
              setUnsavedFeedbackChanges={setUnsavedFeedbackChanges}
            />
          </div>
          <div className="flex w-full border-t border-moon-300 p-6 pr-10">
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
      ) : (
        <div className="mt-12 w-full items-center justify-center">
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

type HumanAnnotationSectionProps = {
  entity: string;
  project: string;
  callID: string;
  humanAnnotationSpecs: tsHumanAnnotationSpec[];
  setUnsavedFeedbackChanges: React.Dispatch<
    React.SetStateAction<Record<string, () => Promise<boolean>>>
  >;
};

const HumanAnnotationSection = ({
  entity,
  project,
  callID,
  humanAnnotationSpecs,
  setUnsavedFeedbackChanges,
}: HumanAnnotationSectionProps) => {
  const [isExpanded, setIsExpanded] = useState(true);
  const sortedVisibleColumns = humanAnnotationSpecs.sort((a, b) =>
    (a.name ?? '').localeCompare(b.name ?? '')
  );

  return (
    <div>
      <HumanAnnotationHeader
        numHumanAnnotationSpecsVisible={sortedVisibleColumns.length}
        numHumanAnnotationSpecsHidden={
          humanAnnotationSpecs.length - sortedVisibleColumns.length
        }
        isExpanded={isExpanded}
        setIsExpanded={setIsExpanded}
      />
      {isExpanded && (
        <HumanAnnotationInputs
          entity={entity}
          project={project}
          callID={callID}
          humanAnnotationSpecs={sortedVisibleColumns}
          setUnsavedFeedbackChanges={setUnsavedFeedbackChanges}
        />
      )}
    </div>
  );
};

type HumanAnnotationHeaderProps = {
  numHumanAnnotationSpecsVisible: number;
  numHumanAnnotationSpecsHidden: number;
  isExpanded: boolean;
  setIsExpanded: (isExpanded: boolean) => void;
};

const HumanAnnotationHeader = ({
  numHumanAnnotationSpecsVisible,
  numHumanAnnotationSpecsHidden,
  isExpanded,
  setIsExpanded,
}: HumanAnnotationHeaderProps) => {
  return (
    <button
      className="text-md hover:bg-gray-100 flex w-full items-center justify-between px-6 py-8 font-semibold"
      onClick={() => setIsExpanded(!isExpanded)}>
      <div className="mb-8 flex w-full items-center">
        <div className="text-lg">Human annotations</div>
        <div className="ml-6 mt-1">
          <DisplayNumericCounter count={numHumanAnnotationSpecsVisible} />
        </div>
        <div className="flex-grow" />
        {numHumanAnnotationSpecsHidden > 0 && (
          <div className="mr-4 mt-2 rounded-full px-2 text-xs font-medium">
            {numHumanAnnotationSpecsHidden} hidden
          </div>
        )}
      </div>
      <div className="mb-6 flex items-center">
        <Icon name={isExpanded ? 'chevron-up' : 'chevron-down'} />
      </div>
    </button>
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
            <div className="bg-gray-50 font-italic mt-4 text-sm text-moon-700 ">
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

const DisplayNumericCounter = ({count}: {count: number}) => {
  return (
    <div className="rounded-sm bg-moon-150 px-2 text-xs font-medium text-moon-500">
      {count}
    </div>
  );
};
