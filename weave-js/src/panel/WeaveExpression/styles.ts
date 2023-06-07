import * as globals from '@wandb/weave/common/css/globals.styles';
import {Button} from 'semantic-ui-react';
import {Editable} from 'slate-react';
import styled, {css} from 'styled-components';

import OpDoc from './OpDoc';

// export const EditableContainer = styled.div<{
//   noBox?: boolean;
//   isInvalid?: boolean;
// }>`
//   position: relative;
//   display: flex;
//   flex: 1 1 auto;
//
//   ${props =>
//     !props.noBox &&
//     css`
//       border: 1px solid;
//       flex-grow: 1;
//       border-color: ${(innerProps: {isInvalid?: boolean}) =>
//         innerProps.isInvalid ? globals.error : '#bbb'};
//       border-radius: 4px;
//       padding: 6px 8px;
//       min-width: 200px;
//     `}
// `;
// EditableContainer.displayName = 'EditableContainer';

// export const WeaveEditable = styled(Editable)<{truncate?: boolean}>`
//   width: 100%;
//   min-height: 20px;
//   line-height: 20px;
//
//   font-family: Inconsolata;
//   cursor: text;
//
//   // Req'd to make editor selectable in Safari
//   user-select: text;
//
//   &.invalid {
//     border-bottom: 1px dotted ${globals.RED};
//   }
//
//   & span.identifier {
//     color: ${globals.MAGENTA};
//   }
//
//   span.property_identifier {
//     color: ${globals.SIENNA_DARK};
//   }
//
//   & span.operator {
//     color: ${globals.SIENNA_DARK};
//   }
//
//   & span.string {
//     color: ${globals.TEAL};
//   }
//
//   & span.number,
//   & span.null {
//     color: ${globals.TEAL};
//   }
//
//   & span.boolean {
//     color: ${globals.TEAL};
//   }
//
//   & span.ACTIVE_NODE {
//     text-decoration: underline dotted rgba(0, 0, 0, 0.2);
//   }
//
//   /* HACK: attempt to hide large object literals
//   & span.large_object {
//     display: none;
//   }
//   */
//
//   ${p =>
//     p.truncate &&
//     css`
//       & > div {
//         white-space: nowrap;
//         overflow: hidden;
//         text-overflow: ellipsis;
//       }
//     `}
// `;
// WeaveEditable.displayName = 'WeaveEditable';

// export const ApplyButton = styled(Button)`
//   display: none;
//   position: absolute;
//   font-size: 13px !important;
//   line-height: 20px !important;
//   padding: 0px 4px !important;
//   height: 20px;
// `;
// ApplyButton.displayName = 'ApplyButton';

export const StyledOpDoc = styled(OpDoc)`
  display: inline-block;
  vertical-align: top;
  margin-left: 5px;

  background-color: #fffeee;
  padding: 10px;
  border-radius: 3px;
  border: 1px solid black;

  max-width: 250px;
`;
StyledOpDoc.displayName = 'StyledOpDoc';
