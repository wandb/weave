import _ from 'lodash';

export type Property = {
  id: string;
  label: string;
  labelSecondary?: string;
  isSelectable?: boolean;
  tooltip?: string;
};

export const PROPERTIES: Property[] = [
  {
    id: 'likesHuggingFace',
    label: 'Hugging Face Likes',
    isSelectable: true,
  },
  {
    id: 'downloadsHuggingFace',
    label: 'Hugging Face Downloads',
    isSelectable: true,
  },
];

export type PropertyId = (typeof PROPERTIES)[number]['id'];
export const PROPERTY_INDEX: Record<PropertyId, Property> = _.keyBy(
  PROPERTIES,
  'id'
);

type Evaluation = {
  id: string;
  label: string;
  labelSecondary?: string;
  type?: 'percentage';
  tooltip?: string;
};

export const EVALUATIONS: Evaluation[] = [
  {
    id: 'artificial_analysis_intelligence_index',
    label: 'Artificial Analysis Intelligence Index',
  },
  {
    id: 'artificial_analysis_coding_index',
    label: 'Artificial Analysis Coding Index',
  },
  {
    id: 'artificial_analysis_math_index',
    label: 'Artificial Analysis Math Index',
  },
  {
    id: 'mmlu_pro',
    label: 'MMLU-Pro',
    labelSecondary: 'Reasoning & Knowledge',
    type: 'percentage',
    tooltip:
      'Advanced Multitask Knowledge and Reasoning Evaluation. An advanced benchmark that tests both broad knowledge and reasoning capabilities across many subjects, featuring challenging questions and multiple-choice answers with increased difficulty and complexity.',
  },
  {
    id: 'gpqa',
    label: 'GPQA Diamond',
    labelSecondary: 'Scientific Reasoning',
    type: 'percentage',
    tooltip:
      'GPQA Diamond is a subset of the larger GPQA (Graduate-Level Google-Proof Q&A Benchmark) dataset, specifically designed to evaluate the reasoning capabilities of advanced AI models. It consists of 198 multiple-choice questions across biology, chemistry, and physics, chosen for their difficulty and the requirement for deep understanding rather than simple recall or search. Experts at PhD level in the corresponding domains reach 65% accuracy.',
  },
  {
    id: 'hle',
    label: "Humanity's Last Exam",
    labelSecondary: 'Reasoning & Knowledge',
    type: 'percentage',
    tooltip:
      "Humanity's Last Exam (HLE) is a multi-modal benchmark at the frontier of human knowledge, designed to be the final closed-ended academic benchmark of its kind with broad subject coverage. Humanity's Last Exam consists of 3,000 questions across dozens of subjects, including mathematics, humanities, and the natural sciences. HLE is developed globally by subject-matter experts and consists of multiple-choice and short-answer questions suitable for automated grading.",
  },
  {
    id: 'livecodebench',
    label: 'LiveCodeBench',
    labelSecondary: 'Coding',
    type: 'percentage',
  },
  {
    id: 'scicode',
    label: 'SciCode',
    labelSecondary: 'Coding',
    type: 'percentage',
    tooltip:
      'SciCode tests the ability of language models to generate code to solve scientific research problems. It assesses models on 65 problems from mathematics, physics, chemistry, biology, and materials science.',
  },
  {
    id: 'math_500',
    label: 'MATH-500',
    labelSecondary: 'Quantitative Reasoning',
    type: 'percentage',
  },
  {
    id: 'aime',
    label: 'AIME 2024',
    labelSecondary: 'Competition Math',
    type: 'percentage',
    tooltip:
      "Problems from the American Invitational Mathematics Examination. A benchmark for evaluating AI's ability to solve challenging mathematics problems from AIME - a prestigious high school mathematics competition.",
  },
];

type TimeMetric = {
  id: string;
  label: string;
  labelSecondary?: string;
  lowerIsBetter: boolean;
};

export const TIME_METRICS: TimeMetric[] = [
  {
    id: 'median_output_tokens_per_second',
    label: 'Median Output Tokens',
    labelSecondary: 'per Second',
    lowerIsBetter: false,
  },
  {
    id: 'median_time_to_first_token_seconds',
    label: 'Median Time to First Token',
    labelSecondary: 'Seconds',
    lowerIsBetter: true,
  },
  {
    id: 'median_time_to_first_answer_token',
    label: 'Median Time to First Answer Token',
    labelSecondary: 'Seconds',
    lowerIsBetter: true,
  },
];
