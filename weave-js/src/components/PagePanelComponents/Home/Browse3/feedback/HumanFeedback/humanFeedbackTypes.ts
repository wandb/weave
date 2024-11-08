import {AnnotationSpec} from '../../pages/wfReactInterface/generatedBaseObjectClasses.zod';
import {Feedback} from '../../pages/wfReactInterface/traceServerClientTypes';

export type tsHumanAnnotationColumn = AnnotationSpec & {
  ref: string;
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
