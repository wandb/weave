import React from 'react';
import {Button, ButtonProps} from '../components/Button';

export interface MagicButtonProps extends Omit<ButtonProps, 'icon' | 'startIcon'> {
  /**
   * Whether the button is in a loading/generating state.
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
  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    if (isGenerating && onCancel) {
      onCancel();
    } else if (onClick) {
      onClick(e);
    }
  };

  const buttonContent = isGenerating ? (
    <>
      <span className="inline-block animate-spin">⟳</span>
      {!iconOnly && <span className="ml-6">Cancel</span>}
    </>
  ) : (
    <>
      <span className={isGenerating ? 'animate-pulse' : ''}>✨</span>
      {!iconOnly && children && <span className="ml-6">{children}</span>}
    </>
  );

  return (
    <Button
      onClick={handleClick}
      disabled={disabled && !isGenerating}
      size={size}
      variant={variant}
      className={`transition-all ${isGenerating ? 'opacity-100' : ''} ${className}`}
      {...restProps}>
      {buttonContent}
    </Button>
  );
}; 