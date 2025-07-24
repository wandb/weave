import _ from 'lodash';
import React, {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
} from 'react';

import {useEntityProject} from '../../context';
import {TraceCallSchema} from '../wfReactInterface/traceServerClientTypes';
import {
  useThreadMessagesLoader,
  useThreadTurns,
} from '../wfReactInterface/tsDataModelHooks';
import {CallChat} from './CallChat';
import {TurnAnchor} from './TurnAnchor';

export interface ThreadChatViewProps {
  threadId: string;
  turnsState: ReturnType<typeof useThreadTurns>['turnsState'];
  onVisibleTurnChange?: (turnIndex: number) => void;
}

export interface ThreadChatViewRef {
  scrollToTurn: (turnId: string) => void;
}

/**
 * ThreadChatView displays thread messages grouped by consecutive turn_id sequences.
 *
 * Handles sequential grouping where calls with the same turn_id that appear
 * consecutively are grouped together, but separate sequences of the same turn_id
 * are kept as separate groups.
 *
 * This component exposes imperative methods through a ref for parent components
 * to interact with the chat view programmatically. It also reports back when
 * the first visible turn changes during scrolling (top-to-bottom detection).
 *
 * @param threadId - The thread identifier
 * @param turnsState - The turns state from useThreadTurns hook
 * @param onVisibleTurnChange - Callback fired when the first visible turn changes during scroll, receives turn index
 *
 * @example
 * ```tsx
 * const chatViewRef = useRef<ThreadChatViewRef>(null);
 *
 * // Scroll to a specific turn
 * chatViewRef.current?.scrollToTurn('turn-123');
 *
 * <ThreadChatView
 *   ref={chatViewRef}
 *   selectedTurnId={selectedTurnId}
 *   threadId="thread123"
 *   turnsState={turnsState}
 *   onVisibleTurnChange={(turnIndex) => console.log('First visible turn index:', turnIndex)}
 * />
 * ```
 */
export const ThreadChatView = forwardRef<
  ThreadChatViewRef,
  ThreadChatViewProps
>(({threadId, turnsState, onVisibleTurnChange}, ref) => {
  const {projectId} = useEntityProject();
  const messagesState = useThreadMessagesLoader(projectId, threadId);

  const turnRefs = useRef<Map<string, HTMLDivElement>>(new Map());
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const currentVisibleTurnIndexRef = useRef<number | null>(null);

  // Group consecutive calls with the same turn_id
  const messageGroups = useMemo(() => {
    if (!messagesState.value) {
      return [];
    }

    return _.groupBy(messagesState.value, 'turn_id');
  }, [messagesState.value]);

  const turnIds = useMemo(() => {
    if (turnsState.loading) {
      return [];
    }

    return turnsState.value?.map(turn => turn.id);
  }, [turnsState]);

  // Debounced callback to report visible turn changes
  const debouncedVisibleTurnChange = useMemo(
    () =>
      _.debounce((turnIndex: number) => {
        if (currentVisibleTurnIndexRef.current !== turnIndex) {
          currentVisibleTurnIndexRef.current = turnIndex;
          onVisibleTurnChange?.(turnIndex);
        }
      }, 1),
    [onVisibleTurnChange]
  );

  // Expose imperative methods to parent components
  useImperativeHandle(
    ref,
    () => ({
      scrollToTurn: (turnId: string) => {
        const turnElement = turnRefs.current.get(turnId);
        if (turnElement) {
          turnElement.scrollIntoView({behavior: 'smooth', block: 'start'});
        }
      },
    }),
    []
  );

  const messageComponents = useMemo(() => {
    if (_.isEmpty(messageGroups) || _.isEmpty(turnIds)) {
      return null;
    }
    return turnIds!.map((turnId, groupIndex: number) => {
      const turnCalls = (messageGroups as Record<string, TraceCallSchema[]>)[
        turnId
      ];
      const hasTurnCalls = !_.isEmpty(turnCalls);
      return (
        <div
          key={`${turnId}-${groupIndex}`}
          data-turn-id={turnId}
          data-turn-index={groupIndex}
          ref={el => {
            if (el) {
              turnRefs.current.set(turnId, el);
            } else {
              turnRefs.current.delete(turnId);
            }
          }}
          className="px-16 py-12 even:bg-moon-100">
          <span className=" mb-8 flex h-18 w-18 items-center justify-center rounded-[20px] bg-moon-200 text-xs font-bold">
            {groupIndex + 1}
          </span>

          {!hasTurnCalls && <TurnAnchor turnId={turnId} />}

          {hasTurnCalls &&
            turnCalls.map((call: TraceCallSchema, callIndex: number) => (
              <CallChat key={callIndex} call={call} showTitle={false} />
            ))}
        </div>
      );
    });
  }, [turnIds, messageGroups]);

  // Set up scroll-based visibility detection
  // Using scroll handler for reliable, predictable turn detection
  useEffect(() => {
    if (!scrollContainerRef.current || !turnIds?.length || !messageComponents) {
      return;
    }

    let scrollHandler: (() => void) | null = null;
    let container: HTMLElement | null = null;

    // Wait a tick to ensure DOM elements are rendered
    const timeoutId = setTimeout(() => {
      // Scroll-based visibility detection for reliable turn tracking
      scrollHandler = _.throttle(() => {
        if (!scrollContainerRef.current || !turnIds?.length) return;

        container = scrollContainerRef.current;
        const containerRect = container.getBoundingClientRect();
        const containerTop = containerRect.top;
        const containerHeight = containerRect.height;

        // Find the first turn that's visible (top edge in viewport)
        let firstVisibleIndex = -1;

        turnRefs.current.forEach((element, turnId) => {
          const rect = element.getBoundingClientRect();
          const elementTop = rect.top;
          const elementBottom = rect.bottom;

          // Check if element intersects with container viewport
          const isVisible =
            elementBottom > containerTop &&
            elementTop < containerTop + containerHeight;

          if (isVisible) {
            const turnIndex = turnIds.findIndex(id => id === turnId);
            if (
              turnIndex >= 0 &&
              (firstVisibleIndex === -1 || turnIndex < firstVisibleIndex)
            ) {
              firstVisibleIndex = turnIndex;
            }
          }
        });

        if (firstVisibleIndex >= 0) {
          debouncedVisibleTurnChange(firstVisibleIndex);
        }
      }, 50); // Reduced throttle for more responsive detection

      if (scrollContainerRef.current) {
        scrollContainerRef.current.addEventListener('scroll', scrollHandler, {
          passive: true,
        });

        // Trigger initial detection
        scrollHandler();
      }
    }, 0);

    return () => {
      clearTimeout(timeoutId);
      if (scrollHandler && container) {
        container!.removeEventListener('scroll', scrollHandler);
        (scrollHandler as any).cancel?.(); // Cancel throttled function
      }
      debouncedVisibleTurnChange.cancel();
    };
  }, [turnIds, messageComponents, debouncedVisibleTurnChange]);

  if (messagesState.loading || turnsState.loading) {
    return <div>Loading thread messages...</div>;
  }

  if (messagesState.error) {
    return <div>Error loading messages: {messagesState.error.message}</div>;
  }

  if (
    messageGroups.length === 0 &&
    !messagesState.loading &&
    !turnsState.loading
  ) {
    return <div>No messages found in this thread.</div>;
  }

  return (
    <div
      ref={scrollContainerRef}
      className="flex h-full flex-col overflow-y-auto">
      {messageComponents}
    </div>
  );
});
