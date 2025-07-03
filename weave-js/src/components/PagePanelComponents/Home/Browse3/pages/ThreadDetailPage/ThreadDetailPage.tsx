import {Button} from '@wandb/weave/components/Button';
import {Icon} from '@wandb/weave/components/Icon';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {FC, useState} from 'react';

import {useEntityProject} from '../../context';
import {SimplePageLayout} from '../common/SimplePageLayout';
import {SplitPanelLeft} from '../common/SplitPanels/SplitPanelLeft';
import {SplitPanelRight} from '../common/SplitPanels/SplitPanelRight';
import {StatusChip} from '../common/StatusChip';
import {ComputedCallStatusType} from '../wfReactInterface/traceServerClientTypes';
import {useThreadTurns} from '../wfReactInterface/tsDataModelHooks';
import {ThreadMetadata} from './ThreadMetadata';
import {ThreadTurnDetails} from './ThreadTurnDetails';
import {ThreadTurnsList} from './ThreadTurnsList';

export interface ThreadDetailHeaderProps {
  threadId: string;
  status?: ComputedCallStatusType;
  onUpClick: () => void;
  onDownClick: () => void;
}

/**
 * ThreadDetailHeader displays the thread title with turn navigation controls.
 *
 * Shows the thread ID with status indicator and up/down navigation buttons
 * for moving between turns within the thread.
 *
 * @param threadId - The ID of the current thread
 * @param status - The status of the thread (e.g., 'success', 'error', 'running')
 * @param onUpClick - Callback function triggered when up button is clicked (previous turn)
 * @param onDownClick - Callback function triggered when down button is clicked (next turn)
 *
 * @example
 * <ThreadDetailHeader
 *   threadId="thread_abc123"
 *   status="success"
 *   onUpClick={() => console.log('Navigate to previous turn')}
 *   onDownClick={() => console.log('Navigate to next turn')}
 * />
 */
export const ThreadDetailHeader: FC<ThreadDetailHeaderProps> = ({
  threadId,
  status,
  onUpClick,
  onDownClick,
}) => {
  return (
    <Tailwind>
      <div className="flex w-full items-center gap-4">
        <div className="flex items-center gap-4">
          <Button
            icon="sort-ascending"
            tooltip="Previous turn"
            variant="ghost"
            onClick={onUpClick}
            className="mr-2"
          />
          <Button
            icon="sort-descending"
            tooltip="Next turn"
            variant="ghost"
            onClick={onDownClick}
          />
        </div>
        <Icon name="forum-chat-bubble" />
        <span className="text-lg font-semibold">{threadId}</span>
        {status && (
          <div className=" h-min ">
            <StatusChip value={status} iconOnly />
          </div>
        )}
      </div>
    </Tailwind>
  );
};

export interface ThreadDetailPageProps {
  threadId: string;
}

/**
 * ThreadDetailPage displays details for a specific thread.
 *
 * This page shows comprehensive information about a thread including:
 * - Thread metadata (ID, status, turn count, etc.)
 * - Timeline of turns within the thread
 * - Performance metrics and latency information
 *
 * @param threadId - The ID of the thread to display
 *
 * @example
 * <ThreadDetailPage threadId="thread_abc123" />
 */
export const ThreadDetailPage: FC<ThreadDetailPageProps> = ({threadId}) => {
  // State for selected turn index
  const [selectedTurnIndex, setSelectedTurnIndex] = useState<number>(0);

  // TODO: Replace with actual status from API/state
  const status: ComputedCallStatusType = 'success';

  const {entity, project} = useEntityProject();

  const {turnsState} = useThreadTurns(`${entity}/${project}`, threadId);

  const turnCount = turnsState.value?.length || 0;

  // Navigation callbacks - navigate between turns
  const handleUpClick = () => {
    if (selectedTurnIndex > 0) {
      setSelectedTurnIndex(selectedTurnIndex - 1);
    }
  };

  const handleDownClick = () => {
    if (selectedTurnIndex < turnCount - 1) {
      setSelectedTurnIndex(selectedTurnIndex + 1);
    }
  };

  const handleTurnSelect = (index: number) => {
    setSelectedTurnIndex(index);
  };

  // Get the currently selected turn ID from the index
  const selectedTurnId = turnsState.value?.[selectedTurnIndex]?.id;

  return (
    <SimplePageLayout
      title={
        <ThreadDetailHeader
          threadId={threadId}
          status={status}
          onUpClick={handleUpClick}
          onDownClick={handleDownClick}
        />
      }
      hideTabsIfSingle
      tabs={[
        {
          label: 'Overview',
          content: (
            <Tailwind style={{height: '100%'}}>
              <div className="flex h-full flex-col">
                {/* Upper part: Thread metadata */}
                <ThreadMetadata turnsState={turnsState} />

                {/* Lower part: Split panel with turns list and main content */}
                <div className="min-h-0 flex-1">
                  <SplitPanelLeft
                    minWidth={250}
                    defaultWidth={300}
                    maxWidth="50%"
                    isDrawerOpen={true} // Always open
                    drawer={
                      <ThreadTurnsList
                        turnsState={turnsState}
                        selectedTurnId={selectedTurnId}
                        onTurnSelect={handleTurnSelect}
                      />
                    }
                    main={
                      <SplitPanelRight
                        minWidth={200}
                        defaultWidth={200}
                        maxWidth="0%" // No right drawer needed
                        isDrawerOpen={false}
                        main={
                          <ThreadTurnDetails
                            selectedTurnId={selectedTurnId}
                            isLoading={turnsState.loading}
                          />
                        }
                      />
                    }
                  />
                </div>
              </div>
            </Tailwind>
          ),
        },
      ]}
    />
  );
};
