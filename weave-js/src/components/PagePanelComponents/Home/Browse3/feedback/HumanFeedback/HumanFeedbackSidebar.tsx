import {useViewerInfo} from '@wandb/weave/common/hooks/useViewerInfo';
import {Button} from '@wandb/weave/components/Button';
import {parseRef} from '@wandb/weave/react';
import {makeRefCall} from '@wandb/weave/util/refs';
import React, {useEffect, useState} from 'react';

import {Icon} from '../../../../../Icon';
import {useCreateBaseObjectInstance} from '../../pages/wfReactInterface/baseObjectClassQuery';
import {projectIdFromParts} from '../../pages/wfReactInterface/tsDataModelHooks';
import {ConfigureHumanFeedback} from './ConfigureHumanFeedback';
import {HumanFeedbackCell, waitForPendingFeedback} from './HumanFeedback';
import {tsHumanAnnotationColumn} from './humanFeedbackTypes';

type HumanFeedbackSidebarProps = {
  feedbackColumns: tsHumanAnnotationColumn[];
  callID: string;
  entity: string;
  project: string;
  onNextCall?: () => void;
};

export const HumanFeedbackSidebar = ({
  feedbackColumns,
  callID,
  entity,
  project,
  onNextCall,
}: HumanFeedbackSidebarProps) => {
  const callRef = makeRefCall(entity, project, callID);
  const {loading: loadingUserInfo, userInfo} = useViewerInfo();
  const createHumanFeedback = useCreateBaseObjectInstance('AnnotationColumn');
  // Initialize column visibility model with all columns enabled
  const [columnVisibilityModel, setColumnVisibilityModel] = useState<
    Record<string, boolean>
  >(feedbackColumns.reduce((acc, col) => ({...acc, [col.ref]: true}), {}));
  const [isExpanded, setIsExpanded] = useState(true);

  // Sort columns so we always get the same order
  const sortedVisibleColumns = feedbackColumns
    .sort((a, b) => (a.name ?? '').localeCompare(b.name ?? ''))
    .filter(col => columnVisibilityModel[col.ref]);

  const handleDone = async () => {
    // Wait for any pending feedback to complete
    await waitForPendingFeedback();
    // Then proceed with the next call
    onNextCall?.();
  };

  const onSaveColumn = (column: tsHumanAnnotationColumn) => {
    const objectRef = parseRef(column.ref);
    return createHumanFeedback({
      obj: {
        project_id: projectIdFromParts({entity, project}),
        object_id: objectRef.artifactName,
        val: column,
      },
    });
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

  if (loadingUserInfo) {
    return null;
  }
  const viewer = userInfo ? userInfo.id : null;

  return (
    <div className="flex h-full flex-col bg-white">
      <div className="justify-left flex w-full border-b border-moon-300 p-12">
        <div className="text-lg font-semibold">Feedback</div>
        <div className="flex-grow" />
        <ConfigureHumanFeedback
          columns={feedbackColumns}
          columnVisibilityModel={columnVisibilityModel}
          setColumnVisibilityModel={setColumnVisibilityModel}
          onSaveColumn={onSaveColumn}
        />
      </div>
      <div className="mx-6 h-full flex-grow overflow-auto">
        <div>
          <button
            className="text-md hover:bg-gray-100 flex w-full items-center justify-between px-6 py-8 font-semibold"
            onClick={() => setIsExpanded(!isExpanded)}>
            <div className="mb-8 flex w-full items-center">
              <div className="text-lg">Human scores</div>
              <div className="bg-gray-200 ml-4 mt-2 rounded-full px-2 text-xs font-medium">
                {sortedVisibleColumns.length}
              </div>
              <div className="flex-grow" />
              <div className="mr-4 mt-2 rounded-full px-2 text-xs font-medium">
                {feedbackColumns.length - sortedVisibleColumns.length} hidden
              </div>
            </div>
            <div className="mb-6 flex items-center">
              <Icon name={isExpanded ? 'chevron-up' : 'chevron-down'} />
            </div>
          </button>
          {isExpanded && (
            <div>
              {sortedVisibleColumns?.map((field, index) => (
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
                      hfColumn={field}
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
          )}
        </div>
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
