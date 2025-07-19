import {Popover} from '@mui/material';
import {MOON_500} from '@wandb/weave/common/css/color.styles';
import {Button} from '@wandb/weave/components';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {
  cloneElement,
  isValidElement,
  useEffect,
  useRef,
  useState,
} from 'react';
import styled from 'styled-components';

import {LLMDropdownLoaded} from '../../../PlaygroundPage/PlaygroundChat/LLMDropdown';
import {
  DEFAULT_REVISION_PLACEHOLDER,
  DEFAULT_TEXTAREA_LINES,
  DEFAULT_TOOLTIP_WIDTH,
  LINE_HEIGHT_PX,
  STATE_RESET_DELAY_MS,
  TEXTAREA_FOCUS_DELAY_MS,
} from '../constants';
import {useMagicContext} from '../index';
import {useMagicGeneration} from '../hooks/useMagicGeneration';
import {
  Completion,
  CompletionResponseFormat,
  EntityProject,
} from '../types';
import {MagicButton} from './MagicButton';

export interface MagicTooltipProps {
  /**
   * Entity project for API calls.
   */
  entityProject?: EntityProject;
  /**
   * Trigger element - typically a MagicButton.
   * Will be cloned with appropriate props for state management.
   * Required when using children pattern.
   */
  children?: React.ReactElement;
  /**
   * Callback for streaming content as it's generated.
   * @param chunk The current chunk string
   * @param accumulation The accumulated content so far
   * @param parsedCompletion The final parsed completion (null until complete)
   * @param isComplete Whether generation is complete
   */
  onStream: (
    chunk: string,
    accumulation: string,
    parsedCompletion: Completion | null,
    isComplete: boolean
  ) => void;
  /**
   * Callback for errors during generation.
   */
  onError?: (error: Error) => void;
  /**
   * Callback for when generation is cancelled.
   */
  onCancel?: () => void;
  /**
   * System prompt for the AI.
   */
  systemPrompt: string;
  /**
   * Placeholder text for the input.
   */
  placeholder?: string;
  /**
   * Placeholder text for the revision input.
   */
  revisionPlaceholder?: string;
  /**
   * Optional content to revise.
   */
  contentToRevise?: string;
  /**
   * Additional context data to provide to the AI (will be JSON stringified).
   */
  additionalContext?: Record<string, any>;
  /**
   * Response format for the AI.
   */
  responseFormat?: CompletionResponseFormat;
  /**
   * Whether to show model selector dropdown.
   */
  showModelSelector?: boolean;
  /**
   * Width of the tooltip (defaults to 350px).
   */
  width?: number;
  /**
   * Height of the textarea in lines (defaults to 7).
   */
  textareaLines?: number;

  // Controlled props for use by MagicButton
  /**
   * Whether the tooltip is open (controlled mode).
   */
  open?: boolean;
  /**
   * Anchor element for positioning (controlled mode).
   */
  anchorEl?: HTMLElement | null;
  /**
   * Callback when tooltip should close (controlled mode).
   */
  onClose?: () => void;
  /**
   * Callback when generation should start (controlled mode).
   */
  onGenerate?: (userInstructions: string) => Promise<void>;
}



/**
 * MagicTooltip provides a minimal tooltip interface for AI content generation.
 * 
 * This component supports two modes:
 * - **Uncontrolled mode**: Pass children as trigger, manages its own state
 * - **Controlled mode**: Pass open/anchorEl/onClose/onGenerate props for external control
 * 
 * Used internally by MagicButton for controlled mode, or standalone for custom triggers.
 *
 * @param props Tooltip configuration
 * @returns A tooltip component with trigger (in uncontrolled mode)
 */
export const MagicTooltip: React.FC<MagicTooltipProps> = ({
  entityProject,
  children,
  onStream,
  onError,
  onCancel,
  systemPrompt,
  placeholder,
  revisionPlaceholder = DEFAULT_REVISION_PLACEHOLDER,
  contentToRevise,
  additionalContext,
  responseFormat,
  showModelSelector = true,
  width = DEFAULT_TOOLTIP_WIDTH,
  textareaLines = DEFAULT_TEXTAREA_LINES,
  // Controlled props
  open: controlledOpen,
  anchorEl: controlledAnchorEl,
  onClose: controlledOnClose,
  onGenerate: controlledOnGenerate,
}) => {
  const {selectedModel, setSelectedModel} = useMagicContext();

  // Determine if we're in controlled mode
  const isControlled = controlledOpen !== undefined;

  // State management - use controlled props if available, otherwise internal state
  const [internalAnchorEl, setInternalAnchorEl] = useState<HTMLElement | null>(
    null
  );
  const [userInstructions, setUserInstructions] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Use the shared generation hook
  const {isGenerating, generate, cancel} = useMagicGeneration({
    entityProject,
    systemPrompt,
    contentToRevise,
    additionalContext,
    responseFormat,
    onStream,
    onError,
    onCancel,
  });

  const anchorEl = isControlled ? controlledAnchorEl : internalAnchorEl;
  const isOpen = isControlled ? controlledOpen : Boolean(anchorEl);

  // Focus textarea when opened
  useEffect(() => {
    if (anchorEl && textareaRef.current) {
      setTimeout(() => textareaRef.current?.focus(), TEXTAREA_FOCUS_DELAY_MS);
    }
  }, [anchorEl]);

  /**
   * Resets state when the tooltip is closed, with a 500ms delay.
   *
   * This effect waits 500ms after the tooltip is closed before resetting user instructions.
   *
   * Examples:
   *   // Closes the tooltip and resets state after 500ms
   *   setAnchorEl(null);
   */
  useEffect(() => {
    if (!anchorEl) {
      const timeout = setTimeout(() => {
        setUserInstructions('');
      }, STATE_RESET_DELAY_MS);
      return () => clearTimeout(timeout);
    }
    return () => {};
  }, [anchorEl]);

  const handleOpen = (event: React.MouseEvent<HTMLElement>) => {
    if (isControlled) {
      // In controlled mode, we don't manage anchorEl internally
      return;
    }
    setInternalAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    if (!isGenerating) {
      if (isControlled) {
        controlledOnClose?.();
      } else {
        setInternalAnchorEl(null);
      }
    }
  };

  const handleCancel = () => {
    cancel();
    if (isControlled) {
      controlledOnClose?.();
    } else {
      setInternalAnchorEl(null);
    }
  };

  const handleGenerate = async () => {
    if (!userInstructions.trim() || isGenerating) return;

    // In controlled mode, delegate to the parent
    if (isControlled && controlledOnGenerate) {
      await controlledOnGenerate(userInstructions);
      return;
    }

    // Close the tooltip immediately
    if (isControlled) {
      controlledOnClose?.();
    } else {
      setInternalAnchorEl(null);
    }

    await generate(userInstructions);
  };

  // Calculate textarea height based on lines
  const textareaHeight = textareaLines * LINE_HEIGHT_PX;

  // Determine button state
  const getButtonState = () => {
    if (isGenerating) return 'generating';
    if (anchorEl) return 'tooltipOpen';
    return 'default';
  };

  // Only render trigger in uncontrolled mode
  const trigger =
    !isControlled && isValidElement(children)
      ? cloneElement(children as React.ReactElement<any>, {
          onClick: isGenerating ? handleCancel : handleOpen,
          // If it's a MagicButton, pass the state
          ...(children.type === MagicButton
            ? {
                state: getButtonState(),
                onCancel: handleCancel,
              }
            : {}),
        })
      : null;

  return (
    <>
      {trigger}

      <Popover
        open={isOpen}
        anchorEl={anchorEl}
        onClose={handleClose}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'left',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'left',
        }}
        sx={{
          '& .MuiPopover-paper': {
            marginTop: '8px',
            borderRadius: '8px',
            boxShadow: '0 4px 16px rgba(0, 0, 0, 0.1)',
          },
        }}>
        <Tailwind>
          <div
            className="dark:bg-gray-900 bg-white p-8"
            style={{width: `${width}px`}}>
            {/* Text area */}
            <textarea
              ref={textareaRef}
              value={userInstructions}
              onChange={e => setUserInstructions(e.target.value)}
              placeholder={contentToRevise ? revisionPlaceholder : placeholder}
              disabled={isGenerating}
              autoFocus
              aria-label="AI generation instructions"
              aria-describedby={contentToRevise ? "revision-instructions" : "generation-instructions"}
              className="dark:border-gray-700 w-full resize-none rounded bg-transparent p-2 text-sm focus:outline-none disabled:opacity-50 dark:text-white"
              style={{height: `${textareaHeight}px`}}
            />

            {/* Bottom bar with model selector and generate button */}
            <div className="mt-2 flex items-center justify-between gap-3  ">
              {/* Model selector (if enabled) */}
              {showModelSelector ? (
                <div className="mr-3 flex-1">
                  <MakeLLMDropdownOutlined className="[&_>_div]:text-xs">
                    <LLMDropdownLoaded
                      value={selectedModel}
                      onChange={(modelId, maxTokens) => {
                        setSelectedModel(modelId);
                      }}
                      isTeamAdmin={false}
                      direction={{horizontal: 'right'}}
                      excludeSavedModels={true}
                      size="small"
                    />
                  </MakeLLMDropdownOutlined>
                </div>
              ) : (
                <div className="flex-1" />
              )}

              {/* Generate button */}
              <Button
                onClick={isGenerating ? handleCancel : handleGenerate}
                disabled={!isGenerating && !userInstructions.trim()}
                size="small"
                variant="primary">
                {isGenerating
                  ? 'Cancel'
                  : contentToRevise
                  ? 'Revise'
                  : 'Generate'}
              </Button>
            </div>
          </div>
        </Tailwind>
      </Popover>
    </>
  );
};

const MakeLLMDropdownOutlined = styled.div`
  & .llm-dropdown > div[class$='control'] {
    outline: none;
    border: 0px;
    box-shadow: none;
    & > div > div {
      color: ${MOON_500} !important;
    }
    // & [class$='indicatorContainer'] {
    //   display: none;
    // }
  }
`;
