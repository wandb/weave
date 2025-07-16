import {Alert} from '@mui/material';
import Markdown from '@wandb/weave/common/components/Markdown';
import * as Colors from '@wandb/weave/common/css/color.styles';
import {hexToRGB} from '@wandb/weave/common/css/utils';
import {Icon} from '@wandb/weave/components/Icon';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import {MagicButton, MagicTooltip} from '@wandb/weave/WBMagician2';
import React, {FC, useState} from 'react';
import styled from 'styled-components';

const Container = styled.div`
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  overflow: hidden;
`;

const Header = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  border-bottom: 1px solid ${Colors.MOON_200};
  flex-shrink: 0;
`;

const EmptyStateContainer = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  width: 100%;
`;

const EmptyStateContent = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  max-width: 500px;
  text-align: center;
`;

const IconCircle = styled.div`
  border-radius: 50%;
  width: 80px;
  height: 80px;
  background-color: ${hexToRGB(Colors.TEAL_300, 0.48)};
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
`;

const ContentContainer = styled.div`
  flex: 1;
  overflow-y: auto;
  padding: 24px;
`;

const MarkdownContainer = styled.div`
  max-width: 1000px;
  margin: 0 auto;

  /* Style for better markdown display */
  h1,
  h2,
  h3,
  h4,
  h5,
  h6 {
    margin-top: 24px;
    margin-bottom: 16px;
    font-weight: 600;
  }

  h1 {
    font-size: 2em;
  }
  h2 {
    font-size: 1.5em;
  }
  h3 {
    font-size: 1.25em;
  }

  p {
    margin-bottom: 16px;
    line-height: 1.6;
  }

  ul,
  ol {
    margin-bottom: 16px;
    padding-left: 24px;
  }

  li {
    margin-bottom: 8px;
  }

  code {
    background-color: ${Colors.MOON_100};
    padding: 2px 4px;
    border-radius: 3px;
    font-family: monospace;
    font-size: 0.9em;
  }

  pre {
    background-color: ${Colors.MOON_100};
    padding: 16px;
    border-radius: 4px;
    overflow-x: auto;
    margin-bottom: 16px;
  }

  blockquote {
    border-left: 4px solid ${Colors.TEAL_300};
    padding-left: 16px;
    margin: 16px 0;
    color: ${Colors.MOON_600};
  }
`;

const useEvaluationAnalysisLLMContext = () => {
  // TODO: Implement actual context gathering from evaluation data
  return 'TODO: Evaluation context will be gathered here';
};

export const MagicEvaluationAnalysis: FC<{
  entity: string;
  project: string;
  evaluationCallId: string;
}> = ({
  entity,
  project,
  evaluationCallId,
}: {
  entity: string;
  project: string;
  evaluationCallId: string;
}) => {
  const [magicSummary, setMagicSummary] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const llmContext = useEvaluationAnalysisLLMContext();

  const handleMagicStream = (content: string, isComplete: boolean) => {
    if (!isComplete) {
      setIsGenerating(true);
      setError(null);
      // Show content without cursor - markdown handles updates smoothly
      setMagicSummary(content);
    } else {
      setMagicSummary(content);
      setIsGenerating(false);
    }
  };

  const handleError = (errorMessage: string) => {
    setError(errorMessage);
    setIsGenerating(false);
  };

  const handleRegenerate = () => {
    setMagicSummary(null);
    setError(null);
  };

  // Empty state
  if (!magicSummary && !isGenerating && !error) {
    return (
      <Container>
        <EmptyStateContainer>
          <EmptyStateContent>
            <IconCircle>
              <Icon name="magic-wand-star" size={32} color={Colors.TEAL_500} />
            </IconCircle>

            <Tailwind>
              <h2 className="mb-3 text-2xl font-semibold text-moon-800">
                Generate Evaluation Analysis
              </h2>

              <p className="mb-6 text-moon-600">
                Use AI to analyze this evaluation run and generate insights
                about model performance, patterns, and potential improvements.
              </p>

              <MagicTooltip
                onStream={handleMagicStream}
                onError={handleError}
                systemPrompt={`You are an expert ML evaluation analyst. Analyze the provided evaluation data and provide clear, actionable insights.

Format your response in markdown with the following sections:

## Summary
A brief overview of the evaluation results.

## Key Metrics
- List important metrics and their values
- Highlight any significant changes or patterns

## Strengths
What the model does well based on the evaluation.

## Areas for Improvement
Specific weaknesses or areas where performance could be enhanced.

## Recommendations
Actionable suggestions for improving model performance.

Be concise but thorough. Use bullet points and clear formatting.

Evaluation context: ${llmContext}`}
                placeholder="Ask specific questions about the evaluation results, or leave empty for a comprehensive analysis..."
                showModelSelector={true}
                width={450}
                textareaLines={6}>
                <MagicButton size="large" icon="magic-wand-star">
                  Generate Analysis
                </MagicButton>
              </MagicTooltip>
            </Tailwind>
          </EmptyStateContent>
        </EmptyStateContainer>
      </Container>
    );
  }

  // Content state
  return (
    <Container>
      <Header>
        <Tailwind>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold text-moon-800">
              Evaluation Analysis
            </h1>
            {isGenerating && (
              <span className="text-sm text-moon-500">Generating...</span>
            )}
          </div>

          <div className="flex items-center gap-2">
            {!isGenerating && (
              <MagicTooltip
                onStream={handleMagicStream}
                onError={handleError}
                systemPrompt={`You are an expert ML evaluation analyst. The user wants to regenerate or ask follow-up questions about the evaluation analysis.

Previous analysis for context:
${magicSummary}

Provide a fresh analysis or answer their specific question. Format your response in markdown.

Evaluation context: ${llmContext}`}
                placeholder="Ask follow-up questions or leave empty to regenerate the analysis..."
                showModelSelector={true}
                width={450}
                textareaLines={4}>
                <MagicButton size="small" variant="secondary">
                  Regenerate
                </MagicButton>
              </MagicTooltip>
            )}
          </div>
        </Tailwind>
      </Header>

      {error && (
        <Tailwind>
          <div className="px-6 pt-4">
            <Alert severity="error" onClose={handleRegenerate}>
              Failed to generate analysis: {error}
            </Alert>
          </div>
        </Tailwind>
      )}

      <ContentContainer>
        <MarkdownContainer>
          <Markdown content={magicSummary || ''} />
        </MarkdownContainer>
      </ContentContainer>
    </Container>
  );
};
