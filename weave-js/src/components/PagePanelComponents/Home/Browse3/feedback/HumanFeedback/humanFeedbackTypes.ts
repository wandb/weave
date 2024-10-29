import {Feedback} from '../../pages/wfReactInterface/traceServerClientTypes';

export type tsHumanFeedbackColumn = HumanFeedbackColumn & {
  ref: string;
};

export type HumanFeedbackColumn = {
  name: string;
  description: string;

  json_schema: Record<string, any>;
  unique_among_creators?: boolean;
  op_scope?: string[];
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
