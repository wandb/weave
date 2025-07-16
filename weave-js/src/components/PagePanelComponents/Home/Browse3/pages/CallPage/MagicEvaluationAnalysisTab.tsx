import {Alert} from '@mui/material';
import Markdown from '@wandb/weave/common/components/Markdown';
import * as Colors from '@wandb/weave/common/css/color.styles';
import {hexToRGB} from '@wandb/weave/common/css/utils';
import {Button} from '@wandb/weave/components/Button';
import {Icon} from '@wandb/weave/components/Icon';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import {makeRefCall} from '@wandb/weave/util/refs';
import {MagicButton, MagicTooltip} from '@wandb/weave/WBMagician2';
import copyToClipboard from 'copy-to-clipboard';
import React, {FC, useEffect, useMemo, useState} from 'react';
import styled from 'styled-components';

import {useEvaluationComparisonState} from '../CompareEvaluationsPage/ecpState';
import {TraceServerClient} from '../wfReactInterface/traceServerClient';
import {useGetTraceServerClientContext} from '../wfReactInterface/traceServerClientContext';
import {Feedback} from '../wfReactInterface/traceServerClientTypes';
import {projectIdFromParts} from '../wfReactInterface/tsDataModelHooks';
import {SYSTEM_PROMPT_FN} from './magicEvaluationAnalysis';

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
  padding: 8px 24px;
  border-bottom: 1px solid ${Colors.MOON_200};
  flex-shrink: 0;
  flex-direction: row;
  height: 52px;
`;

const EmptyStateContainer = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1;
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
  padding: 0px 24px;
  display: flex;
  flex-direction: column;
`;

const MarkdownContainer = styled.div`
  max-width: 1000px;

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

const Footer = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  border-top: 1px solid ${Colors.MOON_200};
  flex-shrink: 0;
  background: white;
  height: 52px;
`;

const PaginationContainer = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
`;

const PaginationText = styled.span`
  font-size: 14px;
  font-weight: 400;
  color: ${Colors.MOON_500};
  min-width: 90px;
  display: flex;
  justify-content: center;
`;

export const MagicEvaluationAnalysisTab: FC<{
  entity: string;
  project: string;
  evaluationCallId: string;
}> = props => {
  return (
    <Tailwind style={{height: '100%', width: '100%'}}>
      <MagicEvaluationAnalysisTabInner {...props} />
    </Tailwind>
  );
};

const MagicEvaluationAnalysisTabInner: FC<{
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
  const [allFeedbacks, setAllFeedbacks] = useState<Feedback[]>([]);
  const [currentVersionIndex, setCurrentVersionIndex] = useState(0);
  const [copySuccess, setCopySuccess] = useState(false);

  const getTsClient = useGetTraceServerClientContext();

  const evaluationComparisonStateQuery = useEvaluationComparisonState(
    entity,
    project,
    [evaluationCallId]
  );
  const systemPrompt = useMemo(() => {
    return SYSTEM_PROMPT_FN({
      evaluationState: evaluationComparisonStateQuery.result,
    });
  }, [evaluationComparisonStateQuery.result]);

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
        if (existingFeedback.length > 0) {
          setAllFeedbacks(existingFeedback);
          if (existingFeedback[0].payload) {
            const analysis = (existingFeedback[0].payload as any).analysis;
            if (analysis) {
              setMagicSummary(analysis);
            }
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

  // Update displayed analysis when version changes
  useEffect(() => {
    if (allFeedbacks.length > 0 && allFeedbacks[currentVersionIndex]) {
      const feedback = allFeedbacks[currentVersionIndex];
      if (feedback.payload) {
        const analysis = (feedback.payload as any).analysis;
        if (analysis) {
          setMagicSummary(analysis);
        }
      }
    }
  }, [currentVersionIndex, allFeedbacks]);

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

        // Reload feedbacks to include the new one
        const updatedFeedbacks = await getMagicAnalysis(
          client,
          entity,
          project,
          evaluationCallId
        );
        setAllFeedbacks(updatedFeedbacks);
        setCurrentVersionIndex(0); // Show the latest version
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

  const handlePreviousVersion = () => {
    if (currentVersionIndex < allFeedbacks.length - 1) {
      setCurrentVersionIndex(currentVersionIndex + 1);
    }
  };

  const handleNextVersion = () => {
    if (currentVersionIndex > 0) {
      setCurrentVersionIndex(currentVersionIndex - 1);
    }
  };

  const handleCopyFeedback = () => {
    if (allFeedbacks.length > 0 && allFeedbacks[currentVersionIndex]) {
      const currentFeedback = allFeedbacks[currentVersionIndex];
      const feedbackData = currentFeedback.payload['analysis'];
      const success = copyToClipboard(feedbackData);
      if (success) {
        setCopySuccess(true);
        setTimeout(() => setCopySuccess(false), 2000);
      }
    }
  };

  // Loading state
  if (isLoading) {
    return (
      <Container>
        <Header style={{borderBottom: 'none'}} />
        <ContentContainer>
          <EmptyStateContainer>
            <div className="text-moon-600">Loading analysis...</div>
          </EmptyStateContainer>
        </ContentContainer>
        <Footer style={{borderTop: 'none'}} />
      </Container>
    );
  }

  // Empty state
  if (!magicSummary && !isGenerating && !error) {
    return (
      <Container>
        <Header style={{borderBottom: 'none'}} />
        <ContentContainer>
          <EmptyStateContainer>
            <EmptyStateContent>
              <IconCircle>
                <Icon
                  name="magic-wand-star"
                  size={32}
                  color={Colors.TEAL_500}
                />
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
                  systemPrompt={systemPrompt}
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
        </ContentContainer>
        <Footer style={{borderTop: 'none'}} />
      </Container>
    );
  }

  // Content state
  return (
    <Container>
      <Header>
        <div className="flex items-center gap-3">
          <p
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
              systemPrompt={systemPrompt}
              placeholder="Ask follow-up questions or leave empty to regenerate the analysis..."
              showModelSelector={true}
              width={450}
              textareaLines={4}>
              <MagicButton size="medium" variant="secondary">
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

      <Footer>
        {allFeedbacks.length > 0 ? (
          <>
            <PaginationContainer>
              <Button
                variant="ghost"
                size="medium"
                onClick={handlePreviousVersion}
                disabled={currentVersionIndex >= allFeedbacks.length - 1}
                icon="chevron-back"
              />
              <PaginationText>
                {allFeedbacks.length - currentVersionIndex} of{' '}
                {allFeedbacks.length} versions
              </PaginationText>
              <Button
                variant="ghost"
                size="medium"
                onClick={handleNextVersion}
                disabled={currentVersionIndex <= 0}
                icon="chevron-next"
              />
            </PaginationContainer>

            <Button
              variant="ghost"
              size="medium"
              onClick={handleCopyFeedback}
              icon={copySuccess ? 'checkmark' : 'copy'}
              tooltip={copySuccess ? 'Copied!' : 'Copy raw feedback'}>
              {copySuccess ? 'Copied' : 'Copy'}
            </Button>
          </>
        ) : (
          <div />
        )}
      </Footer>
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
