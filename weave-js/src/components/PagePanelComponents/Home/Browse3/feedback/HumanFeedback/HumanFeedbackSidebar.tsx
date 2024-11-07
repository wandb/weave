import {useViewerInfo} from '@wandb/weave/common/hooks/useViewerInfo';
import {Button} from '@wandb/weave/components/Button';
import {makeRefCall} from '@wandb/weave/util/refs';
import React, {useState} from 'react';

import {Icon} from '../../../../../Icon';
import {HumanFeedbackCell, waitForPendingFeedback} from './HumanFeedback';
import {tsHumanFeedbackColumn} from './humanFeedbackTypes';

type HumanFeedbackSidebarProps = {
  feedbackColumns: tsHumanFeedbackColumn[];
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

  const [isExpanded, setIsExpanded] = useState(true);
  const feedbackCellCount = feedbackColumns.length ?? 0;

  // Sort columns so we always get the same order
  feedbackColumns.sort((a, b) => a.name.localeCompare(b.name));

  if (loadingUserInfo) {
    return null;
  }

  const viewer = userInfo ? userInfo.id : null;

  const handleDone = async () => {
    // Wait for any pending feedback to complete
    await waitForPendingFeedback();
    // Then proceed with the next call
    onNextCall?.();
  };

  return (
    <div className="flex h-full flex-col bg-white">
      <div className="justify-left flex w-full border-b border-moon-300 p-12">
        <div className="text-lg font-semibold">Feedback</div>
        <div className="flex-grow" />
        {false && (
          // Enable when we have a proper settings page
          <Button icon="settings" size="small" variant="ghost" />
        )}
      </div>
      <div className="mx-6 h-full flex-grow overflow-auto">
        <div>
          <button
            className="text-md hover:bg-gray-100 flex w-full items-center justify-between px-6 py-8 font-semibold"
            onClick={() => setIsExpanded(!isExpanded)}>
            <div className="mb-8 flex items-center">
              <div className="text-lg">Human scores</div>
              <div className="bg-gray-200 ml-4 mt-2 rounded-full px-2 text-xs font-medium">
                {feedbackCellCount}
              </div>
            </div>
            <Icon name={isExpanded ? 'chevron-up' : 'chevron-down'} />
          </button>
          {isExpanded && (
            <div>
              {feedbackColumns?.map((field, index) => (
                <div key={field.ref}>
                  <div className="bg-gray-50 text-md px-6 py-0 font-semibold">
                    {field.name}
                  </div>
                  {field.description && (
                    <div className="bg-gray-50 font-italic px-6 py-4 text-sm text-moon-700 ">
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
