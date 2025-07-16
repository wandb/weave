import {Alert} from '@mui/material';
import Markdown from '@wandb/weave/common/components/Markdown';
import * as Colors from '@wandb/weave/common/css/color.styles';
import {hexToRGB} from '@wandb/weave/common/css/utils';
import {Icon} from '@wandb/weave/components/Icon';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import {makeRefCall} from '@wandb/weave/util/refs';
import {MagicButton, MagicTooltip} from '@wandb/weave/WBMagician2';
import React, {FC, useEffect, useState} from 'react';
import styled from 'styled-components';

import {TraceServerClient} from '../wfReactInterface/traceServerClient';
import {useGetTraceServerClientContext} from '../wfReactInterface/traceServerClientContext';
import {Feedback} from '../wfReactInterface/traceServerClientTypes';
import {projectIdFromParts} from '../wfReactInterface/tsDataModelHooks';

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
  padding: 8px 12px;
  border-bottom: 1px solid ${Colors.MOON_200};
  flex-shrink: 0;
  flex-direction: row;
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
  const [isLoading, setIsLoading] = useState(true);
  const llmContext = useEvaluationAnalysisLLMContext();
  const getTsClient = useGetTraceServerClientContext();

  // Load existing analysis on mount
  useEffect(() => {
    const loadExistingAnalysis = async () => {
      try {
        const client = getTsClient();
        const existingFeedback = await getMagicAnalysis(
          client,
          entity,
          project,
          evaluationCallId
        );
        if (existingFeedback.length > 0 && existingFeedback[0].payload) {
          const analysis = (existingFeedback[0].payload as any).analysis;
          if (analysis) {
            setMagicSummary(analysis);
          }
        }
      } catch (error) {
        console.error('Failed to load existing analysis:', error);
      } finally {
        setIsLoading(false);
      }
    };

    loadExistingAnalysis();
  }, [getTsClient, entity, project, evaluationCallId]);

  const handleMagicStream = async (content: string, isComplete: boolean) => {
    if (!isComplete) {
      setIsGenerating(true);
      setError(null);
      // Show content without cursor - markdown handles updates smoothly
      setMagicSummary(content);
    } else {
      setMagicSummary(content);
      setIsGenerating(false);

      // Save the analysis when generation is complete
      try {
        const client = getTsClient();
        await saveMagicAnalysis(
          client,
          entity,
          project,
          evaluationCallId,
          content
        );
      } catch (error) {
        console.error('Failed to save analysis:', error);
        // Don't show error to user as the analysis was still generated successfully
      }
    }
  };

  const handleError = (error: Error) => {
    setError(error.message);
    setIsGenerating(false);
  };

  const handleRegenerate = () => {
    setMagicSummary(null);
    setError(null);
  };

  // Loading state
  if (isLoading) {
    return (
      <Container>
        <EmptyStateContainer>
          <Tailwind>
            <div className="text-moon-600">Loading analysis...</div>
          </Tailwind>
        </EmptyStateContainer>
      </Container>
    );
  }

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
        <div className="flex items-center gap-3">
          <p
            className="mb-10"
            style={{
              fontWeight: 600,
              marginRight: 10,
              paddingRight: 10,
            }}>
            Generated Evaluation Analysis
          </p>
        </div>

        <div className="flex items-center gap-2">
          {isGenerating ? (
            <span className="text-sm text-moon-500">Generating...</span>
          ) : (
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
      </Header>

      {error && (
        <div className="px-6 pt-4">
          <Alert severity="error" onClose={handleRegenerate}>
            Failed to generate analysis: {error}
          </Alert>
        </div>
      )}

      <ContentContainer>
        <MarkdownContainer>
          <Markdown content={magicSummary || ''} />
        </MarkdownContainer>
      </ContentContainer>
    </Container>
  );
};

const MAGIC_ANALYSIS_FEEDBACK_TYPE = 'wandb.magic_analysis';

const getMagicAnalysis = async (
  client: TraceServerClient,
  entity: string,
  project: string,
  evaluationCallId: string
): Promise<Feedback[]> => {
  const res = await client.feedbackQuery({
    project_id: projectIdFromParts({
      entity: entity,
      project: project,
    }),
    query: {
      $expr: {
        $and: [
          {
            $eq: [
              {$getField: 'weave_ref'},
              {$literal: makeRefCall(entity, project, evaluationCallId)},
            ],
          },
          {
            $eq: [
              {$getField: 'feedback_type'},
              {$literal: MAGIC_ANALYSIS_FEEDBACK_TYPE},
            ],
          },
        ],
      },
    },
    sort_by: [{field: 'created_at', direction: 'desc'}],
  });
  if ('result' in res) {
    return res.result;
  }
  return [];
};

const saveMagicAnalysis = async (
  client: TraceServerClient,
  entity: string,
  project: string,
  evaluationCallId: string,
  analysis: string
) => {
  await client.feedbackCreate({
    project_id: projectIdFromParts({
      entity: entity,
      project: project,
    }),
    weave_ref: makeRefCall(entity, project, evaluationCallId),
    feedback_type: MAGIC_ANALYSIS_FEEDBACK_TYPE,
    payload: {
      analysis: analysis,
    },
  });
};
