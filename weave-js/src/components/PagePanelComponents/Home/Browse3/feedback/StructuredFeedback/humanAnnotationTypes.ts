import {AnnotationSpec} from '../../pages/wfReactInterface/generatedBaseObjectClasses.zod';
import {Feedback} from '../../pages/wfReactInterface/traceServerClientTypes';

export const HUMAN_ANNOTATION_BASE_TYPE = 'wandb.annotation';
export const FEEDBACK_TYPE_OPTIONS = [
  'string',
  'number',
  'boolean',
  'enum',
  'integer',
];
export type FeedbackSchemaType = (typeof FEEDBACK_TYPE_OPTIONS)[number];

export const makeAnnotationFeedbackType = (type: string) =>
  `${HUMAN_ANNOTATION_BASE_TYPE}.${type}`;

export type tsHumanAnnotationSpec = AnnotationSpec & {
  ref: string;
};

export type HumanAnnotationPayload = {
  value: any;
};

export type HumanAnnotation = Feedback & {};
