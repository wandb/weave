import {AnnotationSpec} from '../../pages/wfReactInterface/generatedBaseObjectClasses.zod';
import {Feedback} from '../../pages/wfReactInterface/traceServerClientTypes';

export type tsHumanAnnotationSpec = AnnotationSpec & {
  ref: string;
};

export type HumanAnnotationPayload = {
  value: {
    [key: string]: {
      [key: string]: string | number;
    };
  };
};

export type HumanFeedback = Feedback & {
  payload: HumanAnnotationPayload;
};
