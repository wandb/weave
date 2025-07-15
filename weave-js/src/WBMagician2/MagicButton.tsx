import React from 'react';

import {Button, ButtonProps} from '../components/Button';

export interface MagicButtonProps extends Omit<ButtonProps, 'icon' | 'startIcon'> {
  /**
   * The current state of the magic button.
   */
  state?: 'default' | 'tooltipOpen' | 'generating' | 'error';
  /**
   * Whether the button is in a loading/generating state.
   * @deprecated Use state="generating" instead
   */
  isGenerating?: boolean;
  /**
   * Callback when clicked during generation (acts as cancel).
   */
  onCancel?: () => void;
  /**
   * Whether to show just the icon without text.
   */
  iconOnly?: boolean;
}

/**
 * MagicButton provides a consistent button for AI generation features.
 * It shows a sparkle icon by default and animates during generation.
 * 
 * @param props Button properties
 * @returns A styled button component with magic sparkle icon
 */
export const MagicButton: React.FC<MagicButtonProps> = ({
  state = 'default',
  isGenerating = false,
  onCancel,
  iconOnly = false,
  children,
  onClick,
  disabled,
  className = '',
  size = 'small',
  variant = 'ghost',
  ...restProps
}) => {
  // Support legacy isGenerating prop
  const currentState = isGenerating ? 'generating' : state;
  
  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    if (currentState === 'generating' && onCancel) {
      onCancel();
    } else if (onClick) {
      onClick(e);
    }
  };

  // Determine button content based on state
  const getButtonContent = () => {
    switch (currentState) {
      case 'generating':
        return (
          <>
            <span className="inline-block animate-spin">⟳</span>
            {!iconOnly && <span className="ml-1.5">Cancel</span>}
          </>
        );
      case 'error':
        return (
          <>
            <span className="text-red-500">⚠️</span>
            {!iconOnly && children && <span className="ml-1.5">{children}</span>}
          </>
        );
      case 'tooltipOpen':
        return (
          <>
            <span className="animate-pulse">✨</span>
            {!iconOnly && children && <span className="ml-1.5">{children}</span>}
          </>
        );
      default:
        return (
          <>
            <span>✨</span>
            {!iconOnly && children && <span className="ml-1.5">{children}</span>}
          </>
        );
    }
  };

  // Determine button variant based on state
  const getButtonVariant = () => {
    if (currentState === 'error') return 'destructive';
    if (currentState === 'tooltipOpen') return 'primary';
    return variant;
  };

  // Add state-specific classes
  const stateClasses = {
    generating: 'opacity-100',
    error: 'shake-animation',
    tooltipOpen: 'ring-2 ring-blue-500 ring-offset-2',
    default: ''
  };

  return (
    <Button
      onClick={handleClick}
      disabled={disabled && currentState !== 'generating'}
      size={size}
      variant={getButtonVariant()}
      className={`transition-all ${stateClasses[currentState] || ''} ${className}`}
      {...restProps}>
      {getButtonContent()}
    </Button>
  );
}; 