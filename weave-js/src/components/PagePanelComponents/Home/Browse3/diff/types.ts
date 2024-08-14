import {ObjectPath} from '../pages/CallPage/traverse';

export type RowData = {
  type: number;
  path: ObjectPath;
  left?: any;
  right?: any;
  panels: string[];
};
