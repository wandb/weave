import {Button} from '@wandb/weave/components/Button';
import {Icon} from '@wandb/weave/components/Icon';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {FC, useCallback, useEffect, useRef, useState} from 'react';
import {usePrevious} from 'react-use';

import {useEntityProject} from '../../context';
import {SimplePageLayout} from '../common/SimplePageLayout';
import {SplitPanelLeft} from '../common/SplitPanels/SplitPanelLeft';
import {SplitPanelRight} from '../common/SplitPanels/SplitPanelRight';
import {StatusChip} from '../common/StatusChip';
import {ComputedCallStatusType} from '../wfReactInterface/traceServerClientTypes';
import {useThreadTurns} from '../wfReactInterface/tsDataModelHooks';
import {ThreadChatViewRef, ThreadChatViewStaging} from './ThreadChatView';
import {ThreadMetadata} from './ThreadMetadata';
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
 * - Bidirectional synchronization between turn selection and scroll position
 *
 * The page maintains synchronization between user-initiated turn selection
 * (via navigation buttons or turn list) and scroll-based turn visibility,
 * preventing infinite loops through source-aware state management.
 *
 * Optimized communication: ThreadChatView directly reports turn indices
 * instead of turn IDs, eliminating the need for conversion logic.
 *
 * @param threadId - The ID of the thread to display
 *
 * @example
 * <ThreadDetailPage threadId="thread_abc123" />
 */
export const ThreadDetailPage: FC<ThreadDetailPageProps> = ({threadId}) => {
  // State for selected turn index
  const [selectedTurnIndex, setSelectedTurnIndex] = useState<number>(0);

  // Track the source of selection changes to prevent infinite loops
  const [isScrollTriggered, setIsScrollTriggered] = useState<boolean>(false);

  // TODO: Replace with actual status from API/state
  const status: ComputedCallStatusType = 'success';

  const {entity, project} = useEntityProject();

  const {turnsState} = useThreadTurns(`${entity}/${project}`, threadId);

  const turnCount = turnsState.value?.turnCalls?.length || 0;

  // Ref for ThreadChatView to enable programmatic scrolling
  const chatViewRef = useRef<ThreadChatViewRef>(null);

  // Get the currently selected turn ID from the index
  const selectedTurnId = turnsState.value?.turnCalls?.[selectedTurnIndex]?.id;

  // Track previous selectedTurnId
  const prevSelectedTurnId = usePrevious(selectedTurnId);

  // Handle scroll-initiated turn visibility changes from ThreadChatView
  const handleVisibleTurnChange = useCallback(
    (turnIndex: number) => {
      if (turnIndex !== selectedTurnIndex) {
        setIsScrollTriggered(true);
        setSelectedTurnIndex(turnIndex);
        // Reset the scroll trigger flag after a brief delay to allow state to update
        setTimeout(() => setIsScrollTriggered(false), 0);
      }
    },
    [selectedTurnIndex]
  );

  // Navigation callbacks - navigate between turns (user-initiated)
  const handleUpClick = () => {
    if (selectedTurnIndex > 0) {
      setIsScrollTriggered(false); // Ensure this is user-initiated
      setSelectedTurnIndex(selectedTurnIndex - 1);
    }
  };

  const handleDownClick = () => {
    if (selectedTurnIndex < turnCount - 1) {
      setIsScrollTriggered(false); // Ensure this is user-initiated
      setSelectedTurnIndex(selectedTurnIndex + 1);
    }
  };

  const handleTurnSelect = (index: number) => {
    setIsScrollTriggered(false); // Ensure this is user-initiated
    setSelectedTurnIndex(index);
  };

  // Scroll to turn when selectedTurnId changes due to user interaction
  useEffect(() => {
    // Only scroll if:
    // 1. selectedTurnId exists and actually changed
    // 2. The change was NOT triggered by scrolling (to prevent infinite loops)
    if (
      selectedTurnId &&
      selectedTurnId !== prevSelectedTurnId &&
      !isScrollTriggered
    ) {
      chatViewRef.current?.scrollToTurn(selectedTurnId);
    }
  }, [selectedTurnId, prevSelectedTurnId, isScrollTriggered]);

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
                          <ThreadChatViewStaging
                            ref={chatViewRef}
                            turnsState={turnsState}
                            onVisibleTurnChange={handleVisibleTurnChange}
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
