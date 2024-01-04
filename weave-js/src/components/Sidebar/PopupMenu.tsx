import _ from 'lodash';
import React, {memo, useMemo} from 'react';
import {
  Menu as SemanticMenu,
  MenuItemProps,
  Popup as SemanticPopup,
  StrictMenuItemProps,
  StrictMenuProps,
  StrictPopupProps,
} from 'semantic-ui-react';
import styled from 'styled-components';

import {GRAY_50} from '../../common/css/globals.styles';

export type Section = {
  label: string;
  items: StrictMenuItemProps[];
};

export type PopupMenuProps = Pick<
  StrictPopupProps,
  `trigger` | `position` | `onClose` | `onOpen` | `open`
> &
  Pick<StrictMenuProps, `items`> & {sections?: Section[]};

const PopupMenuComp: React.FC<PopupMenuProps> = ({
  trigger,
  position,
  items = [],
  sections = [],
  onOpen,
  onClose,
  open,
}) => {
  const allItems = useMemo(() => {
    return [...items, ..._.flatten(sections.map(sectionToItems))];

    function sectionToItems(s: Section): MenuItemProps[] {
      return [{header: true, key: s.label, content: s.label}, ...s.items];
    }
  }, [items, sections]);

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
      onOpen={onOpen}
      onClose={onClose}
      open={open}
      content={
        <Menu compact size="small" items={allItems} secondary vertical />
      }
    />
  );
};

/** @deprecated use `@wandb/components/DropdownMenu` instead */
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
      &.header {
        font-weight: 600;
        cursor: auto;
        &:hover {
          background: none;
        }
      }

      svg {
        width: 18px;
        height: 18px;
        margin-right: 8px;
      }
    }
  }
`;
