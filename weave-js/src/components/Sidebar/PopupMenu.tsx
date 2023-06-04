import React, {memo} from 'react';
import {
  Menu as SemanticMenu,
  Popup as SemanticPopup,
  StrictMenuProps,
  StrictPopupProps,
} from 'semantic-ui-react';
import styled from 'styled-components';

import {GRAY_50} from '../../common/css/globals.styles';

export type PopupMenuProps = Pick<StrictPopupProps, `trigger` | `position`> &
  Pick<StrictMenuProps, `items`>;

const PopupMenuComp: React.FC<PopupMenuProps> = ({
  trigger,
  position,
  items,
}) => {
  return (
    <Popup
      basic
      on="click"
      position={position}
      popperModifiers={{
        preventOverflow: {
          // prevent popper from erroneously constraining the popup to the
          // table header
          boundariesElement: 'viewport',
        },
      }}
      trigger={trigger}
      content={<Menu compact size="small" items={items} secondary vertical />}
    />
  );
};

export const PopupMenu = memo(PopupMenuComp);

const Popup = styled(SemanticPopup)`
  &&& {
    padding: 0;
  }
`;

const Menu = styled(SemanticMenu)`
  &&&&& {
    padding: 6px;
    .item {
      display: flex;
      align-items: center;
      font-size: 16px;
      line-height: 24px;
      padding: 6px 8px;
      margin: 0;

      &:hover {
        background-color: ${GRAY_50};
      }

      svg {
        width: 18px;
        height: 18px;
        margin-right: 8px;
      }
    }
  }
`;
