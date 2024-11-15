import {toast} from '@wandb/weave/common/components/elements/Toast';
import {useViewerInfo} from '@wandb/weave/common/hooks/useViewerInfo';
import {Button} from '@wandb/weave/components/Button';
import {Icon} from '@wandb/weave/components/Icon';
import {makeRefCall} from '@wandb/weave/util/refs';
import React, {useState} from 'react';

import {HumanFeedbackCell} from './HumanFeedback';
import {tsHumanAnnotationSpec} from './humanFeedbackTypes';

type FeedbackSidebarProps = {
  humanFeedbackSpecs: tsHumanAnnotationSpec[];
  callID: string;
  entity: string;
  project: string;
};

export const FeedbackSidebar = ({
  humanFeedbackSpecs,
  callID,
  entity,
  project,
}: FeedbackSidebarProps) => {
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
      <div className="mx-6 h-full flex-grow overflow-auto">
        <HumanFeedbackSection
          entity={entity}
          project={project}
          callID={callID}
          humanFeedbackSpecs={humanFeedbackSpecs}
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
    </div>
  );
};

type HumanFeedbackSectionProps = {
  entity: string;
  project: string;
  callID: string;
  humanFeedbackSpecs: tsHumanAnnotationSpec[];
  setUnsavedFeedbackChanges: React.Dispatch<
    React.SetStateAction<Record<string, () => Promise<boolean>>>
  >;
};

const HumanFeedbackSection = ({
  entity,
  project,
  callID,
  humanFeedbackSpecs,
  setUnsavedFeedbackChanges,
}: HumanFeedbackSectionProps) => {
  const [isExpanded, setIsExpanded] = useState(true);
  const sortedVisibleColumns = humanFeedbackSpecs.sort((a, b) =>
    (a.name ?? '').localeCompare(b.name ?? '')
  );

  return (
    <div>
      <HumanFeedbackHeader
        numHumanFeedbackSpecsVisible={sortedVisibleColumns.length}
        numHumanFeedbackSpecsHidden={
          humanFeedbackSpecs.length - sortedVisibleColumns.length
        }
        isExpanded={isExpanded}
        setIsExpanded={setIsExpanded}
      />
      {isExpanded && (
        <HumanFeedbackInputs
          entity={entity}
          project={project}
          callID={callID}
          humanFeedbackSpecs={sortedVisibleColumns}
          setUnsavedFeedbackChanges={setUnsavedFeedbackChanges}
        />
      )}
    </div>
  );
};

type HumanFeedbackHeaderProps = {
  numHumanFeedbackSpecsVisible: number;
  numHumanFeedbackSpecsHidden: number;
  isExpanded: boolean;
  setIsExpanded: (isExpanded: boolean) => void;
};

const HumanFeedbackHeader = ({
  numHumanFeedbackSpecsVisible,
  numHumanFeedbackSpecsHidden,
  isExpanded,
  setIsExpanded,
}: HumanFeedbackHeaderProps) => {
  return (
    <button
      className="text-md hover:bg-gray-100 flex w-full items-center justify-between px-6 py-8 font-semibold"
      onClick={() => setIsExpanded(!isExpanded)}>
      <div className="mb-8 flex w-full items-center">
        <div className="text-lg">Human scores</div>
        <div className="ml-6 mt-1">
          <DisplayNumericCounter count={numHumanFeedbackSpecsVisible} />
        </div>
        <div className="flex-grow" />
        {numHumanFeedbackSpecsHidden > 0 && (
          <div className="mr-4 mt-2 rounded-full px-2 text-xs font-medium">
            {numHumanFeedbackSpecsHidden} hidden
          </div>
        )}
      </div>
      <div className="mb-6 flex items-center">
        <Icon name={isExpanded ? 'chevron-up' : 'chevron-down'} />
      </div>
    </button>
  );
};

type HumanFeedbackInputsProps = {
  entity: string;
  project: string;
  callID: string;
  humanFeedbackSpecs: tsHumanAnnotationSpec[];
  setUnsavedFeedbackChanges: React.Dispatch<
    React.SetStateAction<Record<string, () => Promise<boolean>>>
  >;
};

const HumanFeedbackInputs = ({
  entity,
  project,
  callID,
  humanFeedbackSpecs,
  setUnsavedFeedbackChanges,
}: HumanFeedbackInputsProps) => {
  const callRef = makeRefCall(entity, project, callID);
  const {loading: loadingUserInfo, userInfo} = useViewerInfo();

  if (loadingUserInfo) {
    return null;
  }
  const viewer = userInfo ? userInfo.id : null;

  return (
    <div>
      {humanFeedbackSpecs?.map((field, index) => (
        <div key={field.ref} className="px-16">
          <div className="bg-gray-50 text-md font-semibold">{field.name}</div>
          {field.description && (
            <div className="bg-gray-50 font-italic mt-4 text-sm text-moon-700 ">
              {field.description}
            </div>
          )}
          <div className="pb-8 pt-4">
            <HumanFeedbackCell
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
