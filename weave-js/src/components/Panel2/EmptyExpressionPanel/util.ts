import {MOON_600} from '@wandb/weave/common/css/color.styles';
import {
  IDENTIFER_COLOR,
  OPERATOR_COLOR,
  STRING_COLOR,
} from '@wandb/weave/panel/WeaveExpression/styles';

export const REGULAR_TEXT_COLOR = MOON_600; // #565C66

const RUNS = {text: 'runs', color: IDENTIFER_COLOR};
const SUMMARY = {text: 'summary', color: OPERATOR_COLOR};
const DOT = {text: '.', color: REGULAR_TEXT_COLOR};
const HISTORY = {text: 'history', color: OPERATOR_COLOR};
const CONFIG = {text: 'config', color: OPERATOR_COLOR};
const OPEN_BRACKET = {text: '[', color: REGULAR_TEXT_COLOR};
const CLOSED_BRACKET = {text: ']', color: REGULAR_TEXT_COLOR};
const EMPTY_PICK_KEY = {text: '""', color: STRING_COLOR};

export const runSummaryExpressionText = [RUNS, DOT, SUMMARY];
export const runConfigExpressionText = [RUNS, DOT, CONFIG];
export const runHistoryExpressionText = [RUNS, DOT, HISTORY];
export const runSummaryKeyExpressionText = [
  ...runSummaryExpressionText,
  OPEN_BRACKET,
  EMPTY_PICK_KEY,
  CLOSED_BRACKET,
];
