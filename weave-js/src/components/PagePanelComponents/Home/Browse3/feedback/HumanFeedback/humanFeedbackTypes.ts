import {Feedback} from '../../pages/wfReactInterface/traceServerClientTypes';

export type FeedbackType =
  | BinaryFeedback
  | TextFeedback
  | CategoricalFeedback
  | NumericalFeedback;

export type tsFeedbackType = FeedbackType & {
  ref: string;
  object_id: string;
};

export type HumanFeedbackSpec = {
  feedback_fields: FeedbackType[];
};

export type tsHumanFeedbackSpec = {
  feedback_fields: tsFeedbackType[];
  ref: string;
};

export type BinaryFeedback = FeedbackField & {};

export type TextFeedback = FeedbackField & {
  max_length: number;
};

export type CategoricalFeedback = FeedbackField & {
  options: string[];
};

export type NumericalFeedback = FeedbackField & {
  min: number;
  max: number;
};

type FeedbackField = {
  display_name: string;
  feedback_type: string;

  _type: string;
};

export type HumanAnnotationPayload = {
  annotation_column_ref: string;

  value: {
    [key: string]: {
      [key: string]: string | number;
    };
  };
};

export type HumanFeedback = Feedback & {
  payload: HumanAnnotationPayload;
};
