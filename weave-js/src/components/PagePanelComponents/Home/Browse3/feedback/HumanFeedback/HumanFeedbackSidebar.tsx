import {useViewerInfo} from '@wandb/weave/common/hooks/useViewerInfo';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import {makeRefCall} from '@wandb/weave/util/refs';
import React, {useState} from 'react';

import {Icon} from '../../../../../Icon';
import {HumanFeedbackCell} from './HumanFeedback';
import {tsHumanFeedbackColumn} from './humanFeedbackTypes';

type HumanFeedbackSidebarProps = {
  feedbackColumns: tsHumanFeedbackColumn[];
  callID: string;
  entity: string;
  project: string;
};

export const HumanFeedbackSidebar = ({
  feedbackColumns,
  callID,
  entity,
  project,
}: HumanFeedbackSidebarProps) => {
  const callRef = makeRefCall(entity, project, callID);
  const {loading: loadingUserInfo, userInfo} = useViewerInfo();

  const [isExpanded, setIsExpanded] = useState(true);
  const feedbackCellCount = feedbackColumns.length ?? 0;

  if (loadingUserInfo) {
    return null;
  }

  const viewer = userInfo ? userInfo.id : null;

  return (
    <Tailwind>
      <div className="flex h-full flex-col bg-white">
        <div className="flex w-full justify-center border-b border-moon-300 p-12">
          <h2 className="text-gray-900 text-lg font-semibold">Add feedback</h2>
        </div>
        <div className="mx-6 h-full flex-grow">
          <div>
            <button
              className="text-md text-gray-700 hover:bg-gray-100 flex w-full items-center justify-between px-6 py-8 font-semibold"
              onClick={() => setIsExpanded(!isExpanded)}>
              <div className="flex items-center">
                <span className="">Human scores</span>
                <span className="text-gray-600 bg-gray-200 ml-4 mt-2 rounded-full px-2 text-xs font-medium">
                  {feedbackCellCount}
                </span>
              </div>
              <Icon name={isExpanded ? 'chevron-up' : 'chevron-down'} />
            </button>
            {isExpanded && (
              <div>
                {feedbackColumns?.map((field, index) => (
                  <div key={field.ref}>
                    <h3 className="bg-gray-50 px-6 py-4 text-sm font-semibold text-moon-700">
                      {field.name}
                    </h3>
                    {field.description && (
                      <p className="bg-gray-50 font-italic px-6 py-4 text-sm text-moon-700 ">
                        {field.description}
                      </p>
                    )}
                    <div className="pb-8 pl-6 pr-8 pt-2">
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
      </div>
    </Tailwind>
  );
};
