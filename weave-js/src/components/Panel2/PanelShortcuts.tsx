import React, {useEffect, useRef, useState} from 'react';
import styled from 'styled-components';

import {CardAction, DEFAULT_CARD_ACTIONS} from './EmptyExpressionPanel';

interface IconButtonProps {
  icon?: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  title?: string;
  className?: string;
}

const StyledButton = styled.button`
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  color: var(--wui-color-text-primary, #333);

  &:hover {
    background-color: var(--wui-color-hover, rgba(0, 0, 0, 0.05));
  }

  &:disabled {
    cursor: not-allowed;
    opacity: 0.5;
  }
`;

const IconButton: React.FC<IconButtonProps> = ({
  icon = '⚡',
  onClick,
  disabled = false,
  title,
  className,
}) => {
  return (
    <StyledButton
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={className}
      type="button">
      {icon}
    </StyledButton>
  );
};

const ShortcutContainer = styled.div`
  position: relative;
  display: inline-block;
`;

const ShortcutDropdown = styled.div<{isOpen: boolean}>`
  position: absolute;
  top: 100%;
  left: 0;
  z-index: 100;
  min-width: 350px;
  width: max-content;
  background-color: white;
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  padding: 4px 0;
  display: ${props => (props.isOpen ? 'block' : 'none')};
  margin-top: 4px;
  max-height: 300px;
  overflow-y: auto;
`;

const ShortcutItem = styled.div`
  padding: 8px 12px;
  cursor: pointer;
  display: flex;
  flex-direction: column;

  &:hover {
    background-color: #f5f5f5;
  }
`;

const ShortcutTitle = styled.div`
  font-weight: 500;
  font-size: 14px;
  color: #333;
`;

const ShortcutExpression = styled.div`
  font-family: monospace;
  font-size: 12px;
  color: #666;
  margin-top: 2px;
`;

interface PanelShortcutsProps {
  setEditorValue?: (text: string) => void;
}

export const PanelShortcuts: React.FC<PanelShortcutsProps> = props => {
  const {setEditorValue} = props;
  const [shortcutOpen, setShortcutOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setShortcutOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  const handleShortcutClick = (action: CardAction) => {
    if (setEditorValue) {
      setEditorValue(action.expression);
    }
    setShortcutOpen(false);
  };

  return (
    <ShortcutContainer ref={containerRef}>
      <IconButton
        icon="⚡"
        onClick={() => setShortcutOpen(!shortcutOpen)}
        title="Quick expressions"
      />
      <ShortcutDropdown isOpen={shortcutOpen}>
        {DEFAULT_CARD_ACTIONS.map(action => (
          <ShortcutItem
            key={action.id}
            onClick={() => handleShortcutClick(action)}>
            <ShortcutTitle>{action.title}</ShortcutTitle>
            <ShortcutExpression>{action.expression}</ShortcutExpression>
          </ShortcutItem>
        ))}
      </ShortcutDropdown>
    </ShortcutContainer>
  );
};
