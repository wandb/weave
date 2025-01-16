import {KnownBaseObjectClassType} from '../wfReactInterface/wfDataModelHooksInterface';

export type WFHighLevelObjectVersionFilter = {
  objectName?: string | null;
  baseObjectClass?: KnownBaseObjectClassType | null;
};
