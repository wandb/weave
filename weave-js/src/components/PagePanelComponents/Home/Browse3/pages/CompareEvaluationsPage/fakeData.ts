const generateRandomScore = () =>
  Math.round((Math.random() * 30 + 70) * 100) / 100;

const metrics = ['Accuracy', 'F1 Score', 'Precision', 'Recall', 'AUC-ROC'];
const models = Array.from({length: 200}, (_, i) => `Model ${i + 1}`);

const generateScores = () => {
  const scores: {[key: string]: number} = {};
  metrics.forEach(metric => {
    scores[metric] = generateRandomScore();
  });
  return scores;
};

export const fakeLeaderboardData = {
  models,
  metrics,
  scores: models.reduce((acc, model) => {
    acc[model] = generateScores();
    return acc;
  }, {} as {[key: string]: {[key: string]: number}}),
};
