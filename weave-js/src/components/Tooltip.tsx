import {Popup} from 'semantic-ui-react';
import styled from 'styled-components';

import {
  hexToRGB,
  MOON_650,
  MOON_800,
  OBLIVION,
  WHITE,
} from '../common/css/globals.styles';

export const Tooltip = styled(Popup).attrs({
  basic: true, // This removes the pointing arrow.
  mouseEnterDelay: 500,
  popperModifiers: {
    preventOverflow: {
      // Prevent popper from erroneously constraining the popup.
      // Without this, tooltips in single row table cells get positioned under the cursor,
      // causing them to immediately close.
      boundariesElement: 'viewport',
    },
  },
})`
  && {
    color: ${WHITE};
    background: ${MOON_800};
    border-color: ${MOON_650};
    box-shadow: 0px 4px 6px ${hexToRGB(OBLIVION, 0.2)};
    font-size: 14px;
    line-height: 140%;
    max-width: 300px;
  }
`;
