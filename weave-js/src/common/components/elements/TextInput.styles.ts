import {Input as SemanticInput} from 'semantic-ui-react';
import styled from 'styled-components';

import {
  fontSizeStandard,
  fontWeightStandard,
  gray500,
  lineHeightStandard,
  spu,
} from '../../css/globals.styles';

export const Input = styled(SemanticInput)`
  width: 100%;
`;

export const Label = styled.label`
  display: block;
  font-weight: calc(${fontWeightStandard} * 6);
  font-size: calc(${fontSizeStandard} / 1.222);
  line-height: calc(${lineHeightStandard} / 1.5);
  margin-bottom: calc(${spu} / 2);
`;

export const Sublabel = styled.span`
  color: ${gray500};
`;
