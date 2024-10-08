import {Box} from '@mui/material';
import React, {useState} from 'react';

import {EditableMarkdown} from './EditableMarkdown';
import {fakeLeaderboardData} from './fakeData';
import {LeaderboardGrid} from './LeaderboardGrid';

type LeaderboardPageProps = {
  entity: string;
  project: string;
};

export const LeaderboardPage: React.FC<LeaderboardPageProps> = props => {
  return (
    <LeaderboardPageContent entity={props.entity} project={props.project} />
  );
};

const DEFAULT_DESCRIPTION = `# Leaderboard`;
const EXAMPLE_DESCRIPTION = `# Welcome to the Leaderboard!

This leaderboard showcases the performance of various models across different metrics. Here's a quick guide:

## Metrics Explained

- **Accuracy**: Overall correctness of the model
- **F1 Score**: Balanced measure of precision and recall
- **Precision**: Ratio of true positives to all positive predictions
- **Recall**: Ratio of true positives to all actual positives
- **AUC-ROC**: Area Under the Receiver Operating Characteristic curve

## How to Interpret the Results

1. Higher scores are generally better for all metrics.
2. Look for models that perform well across *multiple* metrics.
3. Consider the trade-offs between different metrics based on your specific use case.

> Note: Click on any cell in the grid to get more detailed information about that specific score.

Happy analyzing!`;

export const LeaderboardPageContent: React.FC<LeaderboardPageProps> = props => {
  const [description, setDescription] = useState(EXAMPLE_DESCRIPTION);
  const [data] = useState(fakeLeaderboardData);

  // const setDescription = useCallback((newDescription: string) => {
  //   setDescriptionRaw(newDescription.trim());
  // }, []);

  const handleCellClick = (
    modelName: string,
    metricName: string,
    score: number
  ) => {
    console.log(`Clicked on ${modelName} for ${metricName}: ${score}%`);
    // TODO: Implement action on cell click
  };

  return (
    <Box display="flex" flexDirection="column" height="100%">
      <Box flexGrow={1} flexShrink={0} maxHeight="50%" overflow="auto">
        <EditableMarkdown
          value={description}
          onChange={setDescription}
          placeholder={DEFAULT_DESCRIPTION}
        />
      </Box>
      <Box
        flexGrow={1}
        display="flex"
        flexDirection="column"
        overflow="hidden"
        minHeight="50%">
        <LeaderboardGrid data={data} onCellClick={handleCellClick} />
      </Box>
    </Box>
  );
};
