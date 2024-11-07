import {Button} from '@wandb/weave/components/Button';
import {Callout} from '@wandb/weave/components/Callout';
import classNames from 'classnames';
import _ from 'lodash';
import React, {useEffect, useMemo, useRef, useState} from 'react';

import {usePlaygroundContext} from '../PlaygroundPage/PlaygroundChat/PlaygroundContext';
import {StyledTextArea} from '../PlaygroundPage/StyledTextarea';
import {MessagePanelPart} from './MessagePanelPart';
import {ShowMoreButton} from './ShowMoreButton';
import {ToolCalls} from './ToolCalls';
import {Message, ToolCallWithResponse} from './types';

type MessagePanelProps = {
  index: number;
  message: Message;
  isStructuredOutput?: boolean;
  isChoice?: boolean;
  isNested?: boolean;
  pendingToolResponseId?: string;
};

export const MessagePanel = ({
  index,
  message,
  isStructuredOutput,
  isChoice,
  isNested,
  // The id of the tool call response that is pending
  // If the tool call response is pending, the editor will be shown automatically
  // and on save the tool call response will be updated and sent to the LLM
  pendingToolResponseId,
}: MessagePanelProps) => {
  const [isShowingMore, setIsShowingMore] = useState(false);
  const [isOverflowing, setIsOverflowing] = useState(false);
  const [isHovering, setIsHovering] = useState(false);
  const [editorHeight, setEditorHeight] = useState<number | null>(
    pendingToolResponseId ? 100 : null
  );
  const contentRef = useRef<HTMLDivElement>(null);

  const {isPlayground} = usePlaygroundContext();
  useEffect(() => {
    if (contentRef.current) {
      setIsOverflowing(contentRef.current.scrollHeight > 400);
    }
  }, [message.content]);

  const isUser = message.role === 'user';
  const isSystemPrompt = message.role === 'system';
  const isTool = message.role === 'tool';
  const hasToolCalls =
    message.tool_calls != null && message.tool_calls.length > 0;
  const hasContent = message.content != null && message.content.length > 0;

  const responseIndexes: number[] | undefined = hasToolCalls
    ? message
        .tool_calls!.map(
          (toolCall: ToolCallWithResponse) => toolCall.response?.original_index
        )
        .filter((idx): idx is number => idx !== undefined)
    : undefined;

  return (
    <div className={classNames('flex gap-8', {'mt-32': !isTool})}>
      {!isNested && (
        <div className="w-40">
          {!isUser && !isTool && (
            <Callout
              size="small"
              icon="robot-service-member"
              color="moon"
              className="h-32 w-32"
            />
          )}
        </div>
      )}

      <div
        className={classNames('relative overflow-visible py-8', {
          'pb-40': isOverflowing && isShowingMore,
          'border-t border-moon-250': isTool,
          'rounded-lg border border-moon-250': isSystemPrompt,
          'bg-cactus-300/[0.24]': isUser,
          'w-3/4': isTool || hasToolCalls || isStructuredOutput || editorHeight,
          'w-full': isSystemPrompt || isNested,
          'max-w-3xl': !(isSystemPrompt || isNested),
          'ml-auto': isUser,
          'mr-auto': !isUser,
        })}
        onMouseEnter={() => setIsHovering(true)}
        onMouseLeave={() => setIsHovering(false)}>
        <div>
          {isSystemPrompt && (
            <div className="flex justify-between px-16">
              <div className="text-base font-semibold">
                {message.role.charAt(0).toUpperCase() + message.role.slice(1)}
              </div>
            </div>
          )}

          {isTool && (
            <div className={classNames(isNested ? '' : 'px-16', 'pb-8')}>
              <div className="text-sm font-semibold text-moon-500">
                Response
              </div>
            </div>
          )}

          <div
            ref={contentRef}
            className={classNames('w-full overflow-y-hidden', {
              'max-h-[400px]': !isShowingMore,
              'max-h-full': isShowingMore,
            })}>
            {isPlayground && editorHeight ? (
              <PlaygroundMessagePanelEditor
                message={message}
                index={index}
                isChoice={isChoice ?? false}
                editorHeight={editorHeight}
                isNested={isNested ?? false}
                pendingToolResponseId={pendingToolResponseId}
                setEditorHeight={setEditorHeight}
              />
            ) : (
              <>
                {hasContent && (
                  <div
                    className={classNames(
                      hasToolCalls ? 'pb-8' : '',
                      ' text-sm',
                      isNested ? '' : 'px-16'
                    )}>
                    {_.isString(message.content) ? (
                      <MessagePanelPart
                        value={message.content}
                        isStructuredOutput={isStructuredOutput}
                      />
                    ) : (
                      message.content!.map((p, i) => (
                        <MessagePanelPart key={i} value={p} />
                      ))
                    )}
                  </div>
                )}
                {hasToolCalls && (
                  <div
                    className={classNames(
                      hasContent ? 'border-t border-moon-250 pt-8' : ''
                    )}>
                    <ToolCalls toolCalls={message.tool_calls!} />
                  </div>
                )}
              </>
            )}
          </div>

          {isOverflowing && !editorHeight && (
            <ShowMoreButton
              isUser={isUser}
              isShowingMore={isShowingMore}
              setIsShowingMore={setIsShowingMore}
            />
          )}

          {/* Playground buttons (retry, edit, delete) */}
          {isPlayground && isHovering && !editorHeight && (
            <PlaygroundMessagePanelButtons
              index={index}
              isChoice={isChoice ?? false}
              isTool={isTool}
              hasContent={hasContent}
              isNested={isNested ?? false}
              contentRef={contentRef}
              setEditorHeight={setEditorHeight}
              responseIndexes={responseIndexes}
            />
          )}
        </div>
      </div>
    </div>
  );
};

type PlaygroundMessagePanelEditorProps = {
  editorHeight: number;
  isNested: boolean;
  pendingToolResponseId?: string;
  message: Message;
  index: number;
  isChoice: boolean;
  setEditorHeight: (height: number | null) => void;
};

const PlaygroundMessagePanelEditor: React.FC<
  PlaygroundMessagePanelEditorProps
> = ({
  index,
  isChoice,
  setEditorHeight,
  editorHeight,
  isNested,
  pendingToolResponseId,
  message,
}) => {
  const {sendMessage, editMessage, editChoice} = usePlaygroundContext();

  const initialContent = useMemo(
    () =>
      _.isString(message.content)
        ? message.content
        : message.content?.join('') ?? '',
    [message.content]
  );

  const [editedContent, setEditedContent] = useState(initialContent);

  useEffect(() => {
    setEditedContent(initialContent);
  }, [initialContent]);

  const handleSave = () => {
    if (isChoice) {
      editChoice?.(index, {
        message: {content: editedContent},
      });
    } else {
      editMessage?.(index, {
        ...message,
        content: editedContent,
      });
    }
    setEditorHeight(null);
  };

  const handleCancel = () => {
    setEditedContent(initialContent);
    setEditorHeight(null);
  };

  return (
    <div
      className={classNames(
        'w-full pt-16 text-sm',
        isNested ? 'px-2' : 'px-16'
      )}>
      <StyledTextArea
        value={editedContent}
        onChange={e => setEditedContent(e.target.value)}
        style={{
          minHeight: `${editorHeight}px`,
        }}
      />
      <div className="z-100 mt-8 flex justify-end gap-8">
        <Button variant="quiet" size="small" onClick={handleCancel}>
          Cancel
        </Button>
        <Button
          variant="primary"
          size="small"
          onClick={
            pendingToolResponseId
              ? () =>
                  sendMessage?.(
                    'tool',
                    editedContent ?? '',
                    pendingToolResponseId
                  )
              : handleSave
          }>
          Save
        </Button>
      </div>
    </div>
  );
};

type PlaygroundMessagePanelButtonsProps = {
  index: number;
  isChoice: boolean;
  isTool: boolean;
  hasContent: boolean;
  isNested: boolean;
  contentRef: React.RefObject<HTMLDivElement>;
  setEditorHeight: (height: number | null) => void;
  responseIndexes?: number[];
};

const PlaygroundMessagePanelButtons: React.FC<
  PlaygroundMessagePanelButtonsProps
> = ({
  index,
  isChoice,
  isTool,
  hasContent,
  isNested,
  contentRef,
  setEditorHeight,
  responseIndexes,
}) => {
  const {deleteMessage, deleteChoice, retry} = usePlaygroundContext();

  return (
    <div
      className={classNames(
        'absolute right-0 flex w-full items-center justify-end pt-20',
        isNested ? 'bottom-0' : 'bottom-[-32px]'
      )}>
      <div className="z-10 flex gap-4 rounded-lg border border-moon-250 bg-white p-4">
        <Button
          variant="quiet"
          size="small"
          startIcon="randomize-reset-reload"
          onClick={() => retry?.(index, isChoice)}
          tooltip={
            !hasContent
              ? 'We currently do not support retrying functions'
              : 'Retry'
          }
          disabled={!hasContent}>
          Retry
        </Button>
        <Button
          variant="quiet"
          size="small"
          startIcon="pencil-edit"
          onClick={() => {
            setEditorHeight(
              contentRef?.current?.clientHeight
                ? // Accounts for padding and save buttons
                  contentRef.current.clientHeight - 56
                : null
            );
          }}
          tooltip={
            !hasContent
              ? 'We currently do not support editing functions'
              : 'Edit'
          }
          disabled={!hasContent}>
          Edit
        </Button>
        <Button
          variant="quiet"
          size="small"
          startIcon="delete"
          onClick={() => {
            if (isChoice) {
              deleteChoice?.(index);
            } else {
              deleteMessage?.(index, responseIndexes);
            }
          }}
          tooltip={
            isTool ? 'Tool responses cannot be deleted' : 'Delete message'
          }
          disabled={isTool}>
          Delete
        </Button>
      </div>
    </div>
  );
};
