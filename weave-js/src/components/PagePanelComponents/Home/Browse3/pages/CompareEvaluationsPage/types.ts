import {EvaluationComparisonData} from './evaluationResults';
import {ScoreDimension} from './evaluations';
import {RangeSelection} from './initialize';

export type EvaluationComparisonState = {
  data: EvaluationComparisonData;
  baselineEvaluationCallId: string;
  comparisonDimension: ScoreDimension;
  rangeSelection: RangeSelection;
  selectedInputDigest?: string;
};
