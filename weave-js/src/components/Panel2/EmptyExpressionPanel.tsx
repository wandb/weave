import React from 'react';
import styled from 'styled-components';

// Container for the entire empty panel
const Container = styled.div`
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  height: 90%;
  padding: 10px 10px;
  margin: 16px 16px;
  background-color: #f7f7f7;
  min-width: 0;
`;

const HeaderSection = styled.div`
  text-align: center;
  margin-bottom: 24px;
`;

const Title = styled.h2`
  font-size: 20px;
  font-weight: 600;
  color: #333;
  margin: 0 0 8px 0;
`;

const Subtitle = styled.p`
  font-size: 14px;
  color: #666;
  margin: 0;
`;

const CardGrid = styled.div`
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 1fr 1fr;
  gap: 16px;
  width: 100%;
`;

const Card = styled.div`
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 12px 4px;
  background-color: #ffffff;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  cursor: pointer;
  transition: all 0.2s ease-in-out;
  border: 1px solid #eaeaea;

  &:hover {
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
    transform: translateY(-2px);
    border-color: #2e78c7;
  }
`;

const CardTitle = styled.h3`
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  text-align: center;
  color: #333;
`;

const CardSubtitle = styled.div`
  margin-top: 8px;
  font-size: 13px;
  color: #888888;
  text-align: center;
  font-family: monospace;
  background-color: #f5f5f5;
  padding: 4px 8px;
  border-radius: 4px;
`;

export type CardAction = {
  title: string;
  expression: string;
  id: string;
};

export const DEFAULT_CARD_ACTIONS: CardAction[] = [
  {
    id: 'config',
    title: 'Explore configuration',
    expression: 'runs.config',
  },
  {
    id: 'summary',
    title: 'View run summaries',
    expression: 'runs.summary',
  },
  {
    id: 'table',
    title: 'View logged table',
    expression: 'runs.summary["table"]',
  },
  {
    id: 'history',
    title: 'View run history',
    expression: 'runs.history',
  },
];

interface EmptyExpressionPanelProps {
  /**
   * Optional card actions to override the defaults
   */
  cardActions?: CardAction[];

  /**
   * Callback function to handle card clicks
   * @param action The card action that was clicked
   */
  onCardClick?: (action: CardAction) => void;

  /**
   * Function to set editor value
   * @param text The text to set in the editor
   */
  setEditorValue?: (text: string) => void;
}

export const EmptyExpressionPanel: React.FC<EmptyExpressionPanelProps> = ({
  cardActions = DEFAULT_CARD_ACTIONS,
  onCardClick,
  setEditorValue,
}) => {
  // Handler for card click events
  const handleCardClick = (action: CardAction) => {
    if (setEditorValue) {
      // Simply set the editor value with the expression
      // The modified WeaveExpression component will handle reprocessing correctly
      setEditorValue(action.expression);
    }

    if (onCardClick) {
      onCardClick(action);
    }
  };

  return (
    <Container>
      <HeaderSection>
        <Title>START WITH AN EXPRESSION</Title>
        <Subtitle>Select a preset to quickly visualize your data</Subtitle>
      </HeaderSection>
      <CardGrid>
        {cardActions.map(action => (
          <Card
            key={action.id}
            onClick={() => handleCardClick(action)}
            role="button"
            aria-label={`Select ${action.title}`}>
            <CardTitle>{action.title}</CardTitle>
            <CardSubtitle>{action.expression}</CardSubtitle>
          </Card>
        ))}
      </CardGrid>
    </Container>
  );
};
