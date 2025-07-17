import React from 'react';

import {Button, ButtonProps} from '../components/Button';

export interface MagicButtonProps extends Omit<ButtonProps, 'startIcon'> {
  /**
   * The current state of the magic button.
   */
  state?: 'default' | 'tooltipOpen' | 'generating' | 'error';
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
  const currentState = state;

  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    if (currentState === 'generating' && onCancel) {
      onCancel();
    } else if (onClick) {
      onClick(e);
    }
  };

  // Determine icon based on state
  const getIcon = () => {
    switch (currentState) {
      case 'generating':
        return 'running-repeat';
      case 'error':
        return 'warning';
      case 'tooltipOpen':
      case 'default':
      default:
        return 'magic-wand-star';
    }
  };

  // Determine button variant based on state
  const getButtonVariant = () => {
    if (currentState === 'error') return 'destructive';
    if (currentState === 'tooltipOpen') return 'secondary';
    if (currentState === 'default') return 'ghost';
    if (currentState === 'generating') return 'secondary';
    return variant;
  };

  // Add state-specific classes
  const stateClasses = {
    generating: '',
    error: '',
    tooltipOpen: '',
    default: '',
  };

  return (
    <Button
      onClick={handleClick}
      disabled={disabled && currentState !== 'generating'}
      size={size}
      variant={getButtonVariant()}
      icon={getIcon()}
      className={`transition-all ${
        stateClasses[currentState] || ''
      } ${className}`}
      {...restProps}>
      {children}
    </Button>
  );
};
