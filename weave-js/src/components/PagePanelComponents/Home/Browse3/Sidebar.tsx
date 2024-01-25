import {
  MEDIUM_BREAKPOINT,
  MOON_250,
  WHITE,
} from '@wandb/weave/common/css/globals.styles';
import {IconName} from '@wandb/weave/components/Icon';
import React from 'react';
import styled from 'styled-components';

import SidebarSection from './SidebarSection';

const StyledSidebar = styled.div`
  background-color: ${WHITE};
  box-sizing: content-box;
  border-right: 1px solid ${MOON_250};
  width: 56px;
  @media only screen and (max-width: ${MEDIUM_BREAKPOINT}px) {
    width: 100%;
    height: 56px;
    border-right: none;
    border-bottom: 1px solid ${MOON_250};
  }
`;
StyledSidebar.displayName = 'S.StyledSidebar';

const SidebarSections = styled.div`
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  position: sticky;
  top: 0;
  @media only screen and (max-width: ${MEDIUM_BREAKPOINT}px) {
    gap: 14px;
    height: 100%;
    overflow-x: auto;
    &::-webkit-scrollbar {
      display: none;
    }
    margin: 0;
    padding: 0 12px;
    flex-direction: row;
    justify-content: space-between;
    align-items: stretch;
  }
`;
SidebarSections.displayName = 'S.SidebarSections';

export type SidebarItem = {
  id: string;
  iconName: IconName;
  name: string;
  nameTooltip?: string;
  path: string;
  // Enables multiple sections with headers
  section?: string;
};

type SidebarProps = {
  selectedItem: string | null;
  items: SidebarItem[][];
};

export const Sidebar = (props: SidebarProps) => {
  if (props.items.length < 2) {
    return null;
  }

  return (
    <StyledSidebar className="fancy-page__sidebar">
      <SidebarSections>
        {props.items.map((sectionItems, i) => (
          <React.Fragment key={'section__' + i}>
            {i !== 0 && (
              <div className="fancy-page__sidebar__sections__divider" />
            )}
            <SidebarSection
              selectedItem={props.selectedItem}
              items={sectionItems}
            />
          </React.Fragment>
        ))}
      </SidebarSections>
    </StyledSidebar>
  );
};
