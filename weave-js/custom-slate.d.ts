// See https://docs.slatejs.org/concepts/12-typescript
// TODO(np): These are incomplete!  A recent Slate update
// requires users to properly define these types; that we
// didn't necessitates casting to any in many places
import {BaseEditor, Descendant, Point, Range} from 'slate';
import {ReactEditor} from 'slate-react';
import {HistoryEditor} from 'slate-history';
type CustomEditor = {
  type?: string;
  text?: string;
  activeNodeRange?: Range | null;
  shiftPressed?: boolean;
};

type CustomText = {
  type?: string;
  text: string;
};

type CustomRange = {
  anchor: Point;
  focus: Point;
  ACTIVE_NODE?: boolean;
  tempInlineComment?: boolean;
};

type CustomElement = {
  type?: string;
  children: Descendant[];
  [key: string]: any;
};

declare module 'slate' {
  interface CustomTypes {
    Editor: BaseEditor & ReactEditor & HistoryEditor & CustomEditor;
    Element: CustomElement;
    Text: CustomText;
    Range: CustomRange;
  }
}
