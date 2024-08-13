import {Box} from '@mui/material';
import React from 'react';
import styled from 'styled-components';

import {parseRef} from '../../../../react';
import {ValueViewNumber} from '../Browse3/pages/CallPage/ValueViewNumber';
import {ValueViewPrimitive} from '../Browse3/pages/CallPage/ValueViewPrimitive';
import {isRef} from '../Browse3/pages/common/util';
import {useWFHooks} from '../Browse3/pages/wfReactInterface/context';
import {CellValueBoolean} from './CellValueBoolean';
import {CellValueImage} from './CellValueImage';
import {CellValueString} from './CellValueString';
import {SmallRef} from './SmallRef';

type CellValueProps = {
  value: any;
  isExpanded?: boolean;
};

const Collapsed = styled.div<{hasScrolling: boolean}>`
  min-height: 38px;
  line-height: 38px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: ${props => (props.hasScrolling ? 'pointer' : 'default')};
`;
Collapsed.displayName = 'S.Collapsed';

export const CellValue = ({value, isExpanded = false}: CellValueProps) => {
  if (value === undefined) {
    return null;
  }
  if (value === null) {
    return <ValueViewPrimitive>null</ValueViewPrimitive>;
  }
  if (isRef(value)) {
    return <SmallRef objRef={parseRef(value)} iconOnly={isExpanded} />;
  }
  if (typeof value === 'boolean') {
    return (
      <Box
        sx={{
          textAlign: 'center',
          width: '100%',
        }}>
        <CellValueBoolean value={value} />
      </Box>
    );
  }
  if (typeof value === 'string') {
    if (value.startsWith('data:image/')) {
      return <CellValueImage value={value} />;
    }
    return <CellValueString value={value} />;
  }
  if (typeof value === 'number') {
    return (
      <Box
        sx={{
          textAlign: 'right',
          width: '100%',
        }}>
        <ValueViewNumber value={value} fractionDigits={4} />
      </Box>
    );
  }
  // if (isCustomWeaveObject(value)) {
  //   return <CellValueCustomWeaveObject value={value} />;
  // }
  return <CellValueString value={JSON.stringify(value)} />;
};

// type CustomWeaveObject = {
//   _type: 'CustomWeaveType';
//   weave_type: {
//     type: string;
//   };
//   files: {[filename: string]: string};
//   load_op?: string;
// };

// type CustomWeaveObjectImage = {
//   _type: 'CustomWeaveType';
//   weave_type: {
//     type: 'Image';
//   };
//   files: {'image.png': string};
//   load_op?: string;
// };

// const isCustomWeaveObject = (value: any): value is CustomWeaveObject => {
//   return typeof value === 'object' && value._type === 'CustomWeaveType';
// };

// const isCustomWeaveObjectImage = (
//   value: CustomWeaveObject
// ): value is CustomWeaveObjectImage => {
//   return value.weave_type.type === 'Image';
// };

// const CellValueCustomWeaveObject: React.FC<{value: CustomWeaveObject}> = ({
//   value,
// }) => {
//   // TODO: Make this a bit more dynamic
//   const defaultTitle = 'Serialized Weave Object: ' + value.weave_type.type;

//   if (isCustomWeaveObjectImage(value)) {
//     return <CellValueCustomWeaveObjectImage value={value} />;
//   }

//   return <CellValueString value={defaultTitle} />;
// };

// const CellValueCustomWeaveObjectImage: React.FC<{
//   value: CustomWeaveObjectImage;
// }> = ({value}) => {
//   const {useFileContent} = useWFHooks();
//   const content = useFileContent(value.files['image.png']);

//   console.log(value);
//   return <div>Image!</div>;
// };
