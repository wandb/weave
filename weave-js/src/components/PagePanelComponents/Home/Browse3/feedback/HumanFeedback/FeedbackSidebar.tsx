import {useViewerInfo} from '@wandb/weave/common/hooks/useViewerInfo';
import {Button} from '@wandb/weave/components/Button';
import {Icon} from '@wandb/weave/components/Icon';
import {parseRef} from '@wandb/weave/react';
import {makeRefCall} from '@wandb/weave/util/refs';
import React, {useEffect, useState} from 'react';

import {useCreateBaseObjectInstance} from '../../pages/wfReactInterface/baseObjectClassQuery';
import {AnnotationSpec} from '../../pages/wfReactInterface/generatedBaseObjectClasses.zod';
import {projectIdFromParts} from '../../pages/wfReactInterface/tsDataModelHooks';
import {HumanFeedbackCell, waitForPendingFeedback} from './HumanFeedback';
import {tsHumanAnnotationSpec} from './humanFeedbackTypes';
import {ManageHumanFeedback} from './ManageHumanFeedback';

type FeedbackSidebarProps = {
  humanFeedbackSpecs: tsHumanAnnotationSpec[];
  callID: string;
  entity: string;
  project: string;
  onNextCall?: () => void;
};

export const FeedbackSidebar = ({
  humanFeedbackSpecs,
  callID,
  entity,
  project,
  onNextCall,
}: FeedbackSidebarProps) => {
  // Initialize column visibility model with all columns enabled
  const humanFeedbackMap = humanFeedbackSpecs.reduce(
    (acc, col) => ({...acc, [col.ref]: true}),
    {}
  );
  const [feedbackVisibilityModel, setFeedbackVisibilityModel] =
    useState<Record<string, boolean>>(humanFeedbackMap);

  const handleDone = async () => {
    // Wait for any pending feedback to complete
    await waitForPendingFeedback();
    onNextCall?.();
  };
  // handle shift + down arrow key, capture so the other handler
  // doesn't also trigger.
  useEffect(() => {
    const handleArrowDownKey = (event: KeyboardEvent) => {
      if (event.shiftKey && event.key === 'ArrowDown') {
        event.preventDefault();
        handleDone();
      }
    };
    const handleArrowUpKey = (event: KeyboardEvent) => {
      if (event.key === 'ArrowUp') {
        event.preventDefault();
        handleDone();
      }
    };
    document.addEventListener('keydown', handleArrowDownKey);
    window.addEventListener('keydown', handleArrowUpKey);
    return () => {
      document.removeEventListener('keydown', handleArrowDownKey);
      window.removeEventListener('keydown', handleArrowUpKey);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="flex h-full flex-col bg-white">
      <FeedbackSidebarHeader
        entity={entity}
        project={project}
        humanFeedbackSpecs={humanFeedbackSpecs}
        columnVisibilityModel={feedbackVisibilityModel}
        setColumnVisibilityModel={setFeedbackVisibilityModel}
      />
      <div className="mx-6 h-full flex-grow overflow-auto">
        <HumanFeedbackSection
          entity={entity}
          project={project}
          callID={callID}
          humanFeedbackSpecs={humanFeedbackSpecs}
          columnVisibilityModel={feedbackVisibilityModel}
        />
      </div>
      <div className="mr-4 border-t border-moon-300 p-12">
        <Button
          onClick={handleDone}
          variant="primary"
          className="w-full"
          size="large"
          endIcon="chevron-next">
          Done
        </Button>
      </div>
    </div>
  );
};

type FeedbackSidebarHeaderProps = {
  entity: string;
  project: string;
  humanFeedbackSpecs: tsHumanAnnotationSpec[];
  columnVisibilityModel: Record<string, boolean>;
  setColumnVisibilityModel: (model: Record<string, boolean>) => void;
};

const FeedbackSidebarHeader = ({
  entity,
  project,
  humanFeedbackSpecs,
  columnVisibilityModel,
  setColumnVisibilityModel,
}: FeedbackSidebarHeaderProps) => {
  const createHumanFeedback = useCreateBaseObjectInstance('AnnotationSpec');

  const onSaveSpec = (spec: tsHumanAnnotationSpec | AnnotationSpec) => {
    if (!('ref' in spec)) {
      throw new Error('Feedback spec must have a ref to save in the sidebar.');
    }
    const objectRef = parseRef(spec.ref);
    return createHumanFeedback({
      obj: {
        project_id: projectIdFromParts({entity, project}),
        object_id: objectRef.artifactName,
        val: spec,
      },
    });
  };

  return (
    <div className="justify-left flex w-full border-b border-moon-300 p-12">
      <div className="text-lg font-semibold">Feedback</div>
      <div className="flex-grow" />
      <ManageHumanFeedback
        specs={humanFeedbackSpecs}
        columnVisibilityModel={columnVisibilityModel}
        setColumnVisibilityModel={setColumnVisibilityModel}
        onSaveSpec={onSaveSpec}
      />
    </div>
  );
};

type HumanFeedbackSectionProps = {
  entity: string;
  project: string;
  callID: string;
  humanFeedbackSpecs: tsHumanAnnotationSpec[];
  columnVisibilityModel: Record<string, boolean>;
};

const HumanFeedbackSection = ({
  entity,
  project,
  callID,
  humanFeedbackSpecs,
  columnVisibilityModel,
}: HumanFeedbackSectionProps) => {
  const [isExpanded, setIsExpanded] = useState(true);
  const sortedVisibleColumns = humanFeedbackSpecs
    .sort((a, b) => (a.name ?? '').localeCompare(b.name ?? ''))
    .filter(col => columnVisibilityModel[col.ref]);

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
        <div className="bg-gray-200 ml-4 mt-2 rounded-full px-2 text-xs font-medium">
          {numHumanFeedbackSpecsVisible}
        </div>
        <div className="flex-grow" />
        <div className="mr-4 mt-2 rounded-full px-2 text-xs font-medium">
          {numHumanFeedbackSpecsHidden} hidden
        </div>
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
};

const HumanFeedbackInputs = ({
  entity,
  project,
  callID,
  humanFeedbackSpecs,
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
        <div key={field.ref}>
          <div className="bg-gray-50 text-md px-6 font-semibold">
            {field.name}
          </div>
          {field.description && (
            <div className="bg-gray-50 font-italic mt-4 px-6 text-sm text-moon-700 ">
              {field.description}
            </div>
          )}
          <div className="pb-8 pl-6 pr-8 pt-4">
            <HumanFeedbackCell
              focused={index === 0}
              hfSpec={field}
              callRef={callRef}
              entity={entity}
              project={project}
              viewer={viewer}
              readOnly={false}
            />
          </div>
        </div>
      ))}
    </div>
  );
};
