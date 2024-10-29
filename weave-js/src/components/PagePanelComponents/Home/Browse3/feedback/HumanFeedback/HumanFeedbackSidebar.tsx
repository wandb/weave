import {Tailwind} from '@wandb/weave/components/Tailwind';
import {makeRefCall} from '@wandb/weave/util/refs';
import React, {useState} from 'react';

import {Icon} from '../../../../../Icon';
import {StructuredFeedbackCell} from './HumanFeedback';
import {tsHumanFeedbackSpec} from './humanFeedbackTypes';

type HumanFeedbackSidebarProps = {
  feedbackOptions: tsHumanFeedbackSpec | null;
  callID: string;
  entity: string;
  project: string;
};

export const HumanFeedbackSidebar = ({
  feedbackOptions,
  callID,
  entity,
  project,
}: HumanFeedbackSidebarProps) => {
  const feedbackFields = feedbackOptions?.feedback_fields;
  const feedbackSpecRef = feedbackOptions?.ref;
  const callRef = makeRefCall(entity, project, callID);
  const [isExpanded, setIsExpanded] = useState(true);

  const feedbackCount = feedbackFields?.length ?? 0;

  if (!feedbackSpecRef) {
    return null;
  }

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
                  {feedbackCount}
                </span>
              </div>
              <Icon name={isExpanded ? 'chevron-up' : 'chevron-down'} />
            </button>
            {isExpanded && (
              <div>
                {feedbackFields?.map((field, index) => (
                  <div key={field.ref}>
                    <h3 className="text-gray-700 bg-gray-50 px-6 py-4 text-sm font-semibold">
                      {field.display_name}
                    </h3>
                    <div className="pb-8 pl-6 pr-8 pt-2">
                      <StructuredFeedbackCell
                        focused={index === 0}
                        sfData={field}
                        callRef={callRef}
                        entity={entity}
                        project={project}
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
