/**
 * Contains common components and utilities for building config panels.
 * I expect this file to mature and eventually become a general-purpose
 * Weave graph editor.
 */

import ModifiedDropdown from '@wandb/weave/common/components/elements/ModifiedDropdown';
import NumberInput from '@wandb/weave/common/components/elements/NumberInput';
import {TextInput} from '@wandb/weave/common/components/elements/TextInput';
import * as globals from '@wandb/weave/common/css/globals.styles';
import * as _ from 'lodash';
import React, {FC, ReactNode, useCallback, useState} from 'react';
import {MenuItemProps} from 'semantic-ui-react';
import styled, {css, ThemeProvider} from 'styled-components';

import {useWeaveSidebarConfigStylingEnabled} from '../../../context';
import {WeaveExpression} from '../../../panel/WeaveExpression';
import {IconButton} from '../../IconButton';
import {PopupMenu} from '../../Sidebar/PopupMenu';
import {themes} from '../Editor.styles';
import {IconOverflowHorizontal} from '../Icons';
import {IconDown as IconDownUnstyled} from '../Icons';
import * as S from './styles';
import * as SN from './stylesNew';

export const ChildConfigContainer = styled.div`
  position: relative;
  padding-left: 2px;

  &:before {
    content: '';
    position: absolute;
    top: 12px;
    bottom: 12px;
    left: 0;
    width: 2px;
    background-color: ${globals.GRAY_350};
  }
`;
ChildConfigContainer.displayName = 'S.ChildConfigContainer';

export const ConfigSectionContainer = styled.div`
  padding: 12px;
  &:not(:first-child) {
    border-top: 1px solid ${globals.GRAY_350};
  }
`;
ConfigSectionContainer.displayName = 'S.ConfigSectionContainer';

export const ConfigSectionHeader = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
  cursor: pointer;
`;
ConfigSectionHeader.displayName = 'S.ConfigSectionHeader';

export const ConfigSectionHeaderButton = styled.div<{expanded: boolean}>`
  display: flex;
  transform: rotate(${p => (p.expanded ? 0 : 180)}deg);
  margin-left: 8px;
`;
ConfigSectionHeaderButton.displayName = 'S.ConfigSectionHeaderButton';

export const ConfigSectionOptions = styled.div`
  display: flex;
  flex-direction: column;
`;
ConfigSectionOptions.displayName = 'S.ConfigSectionOptions';

type ConfigSectionProps = {
  label?: string;
  menuItems?: MenuItemProps[];
};

export const ConfigSection: FC<ConfigSectionProps> = ({
  label,
  children,
  menuItems,
}) => {
  const [expanded, setExpanded] = useState(true);

  const toggleExpanded = useCallback(() => {
    setExpanded(prev => !prev);
  }, []);

  return (
    <ConfigSectionContainer>
      {label && (
        <ConfigSectionHeader onClick={toggleExpanded}>
          {label}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
            }}>
            {menuItems != null && menuItems.length > 0 && (
              <PopupMenu
                position="bottom right"
                trigger={
                  <ConfigDimMenuButton
                    onClick={e => {
                      e.stopPropagation();
                    }}>
                    <IconOverflowHorizontal />
                  </ConfigDimMenuButton>
                }
                items={menuItems}
              />
            )}
            <ConfigSectionHeaderButton expanded={expanded}>
              <IconDown />
            </ConfigSectionHeaderButton>
          </div>
        </ConfigSectionHeader>
      )}
      {expanded && <ConfigSectionOptions>{children}</ConfigSectionOptions>}
    </ConfigSectionContainer>
  );
};

export const ConfigOption: React.FC<
  {
    label: string;
    // component to append after the config component, on the same line, such as
    // "add new y" buttons or "delete option" buttons. see panelplot config y for
    // an example.
    postfixComponent?: React.ReactElement;
  } & {[key: string]: any}
> = props => {
  const sidebarConfigStylingEnabled = useWeaveSidebarConfigStylingEnabled();

  if (sidebarConfigStylingEnabled) {
    return <ConfigOptionNew {...props} />;
  }

  return (
    <S.ConfigOption
      {..._.omit(props, ['label', 'children', 'postfixComponent'])}>
      {props.label !== '' ? (
        <S.ConfigOptionLabel>{props.label}</S.ConfigOptionLabel>
      ) : (
        <></>
      )}
      <S.ConfigOptionField>{props.children}</S.ConfigOptionField>
      {props.postfixComponent}
    </S.ConfigOption>
  );
};

const ConfigOptionNew: React.FC<
  {
    label: string;
    actions?: ReactNode;
    multiline?: boolean;
    // component to append after the config component, on the same line, such as
    // "add new y" buttons or "delete option" buttons. see panelplot config y for
    // an example.
    postfixComponent?: React.ReactElement;
  } & {[key: string]: any}
> = props => {
  const {
    label,
    actions,
    multiline = false,
    postfixComponent,
    children,
    ...restProps
  } = props;
  const labelField = multiline ? (
    <SN.PostfixContainerWrap>
      <SN.ConfigOptionLabel>{label}</SN.ConfigOptionLabel>
      <SN.PostfixContainer>{postfixComponent}</SN.PostfixContainer>
    </SN.PostfixContainerWrap>
  ) : (
    <SN.ConfigOptionLabel>{label}</SN.ConfigOptionLabel>
  );
  return (
    <SN.ConfigOption multiline={multiline} {...restProps}>
      {label && labelField}
      {actions != null && (
        <SN.ConfigOptionActions>{actions}</SN.ConfigOptionActions>
      )}
      <SN.ConfigOptionField>{children}</SN.ConfigOptionField>
      {!multiline && postfixComponent}
    </SN.ConfigOption>
  );
};

export const ModifiedDropdownConfigField: React.FC<
  React.ComponentProps<typeof ModifiedDropdown>
> = props => {
  const sidebarConfigStylingEnabled = useWeaveSidebarConfigStylingEnabled();

  if (sidebarConfigStylingEnabled) {
    return (
      <ConfigFieldWrapper withIcon>
        <ConfigFieldModifiedDropdown
          {...props}
          selection={undefined}
          compact
          icon={<IconDown />}
        />
      </ConfigFieldWrapper>
    );
  }

  return (
    <ModifiedDropdown style={{flex: '1 1 auto', width: '100%'}} {...props} />
  );
};

export const NumberInputConfigField: React.FC<
  React.ComponentProps<typeof NumberInput>
> = props => {
  return (
    <NumberInput
      containerStyle={{flex: '1 1 auto', width: '100%'}}
      inputStyle={{width: '100%'}}
      {...props}
    />
  );
};

export const ExpressionConfigField: React.FC<
  React.ComponentProps<typeof WeaveExpression>
> = props => {
  const sidebarConfigStylingEnabled = useWeaveSidebarConfigStylingEnabled();

  const wrap = (content: ReactNode) =>
    sidebarConfigStylingEnabled ? (
      <ConfigFieldWrapper>{content}</ConfigFieldWrapper>
    ) : (
      <div style={{flex: '1 1 auto', width: '100%'}}>{content}</div>
    );

  return wrap(
    <ThemeProvider theme={themes.light}>
      <WeaveExpression
        noBox={true}
        setExpression={props.setExpression}
        expr={props.expr}
        liveUpdate={!sidebarConfigStylingEnabled}
      />
    </ThemeProvider>
  );
};

export const TextInputConfigField: React.FC<
  React.ComponentProps<typeof TextInput>
> = props => {
  const sidebarConfigStylingEnabled = useWeaveSidebarConfigStylingEnabled();

  const wrap = (content: ReactNode) =>
    sidebarConfigStylingEnabled ? (
      <ConfigFieldWrapper>{content}</ConfigFieldWrapper>
    ) : (
      <div style={{flex: '1 1 auto', width: '100%'}}>{content}</div>
    );

  return wrap(<TextInput {...props} />);
};

export const ConfigFieldWrapper = styled.div<{withIcon?: boolean}>`
  border-radius: 4px;
  flex: 1 1 auto;
  display: flex;
  width: 100%;
  padding: 4px 12px;
  ${p =>
    p.withIcon &&
    css`
      padding-right: 5px;
    `}

  background-color: ${globals.GRAY_25};
  svg {
    color: ${globals.GRAY_500};
  }
  &:hover {
    background-color: ${globals.GRAY_50};
    svg {
      color: ${globals.GRAY_800};
    }
  }
  border: 2px solid transparent;
  &:focus-within {
    border: 2px solid ${globals.TEAL_400};
  }
`;
ConfigFieldWrapper.displayName = 'S.ConfigFieldWrapper';

export const ConfigFieldModifiedDropdown = styled(ModifiedDropdown)`
  &&& {
    width: 100%;
    display: inline-flex;
    align-items: center;
    justify-content: space-between;
    line-height: 20px;
    padding: 0;

    input {
      height: 100%;
      width: 100% !important;
    }
    && > input {
      cursor: pointer;
    }
    && > .text {
      cursor: pointer;
    }
    && > .menu {
      width: calc(100% + 19px);
      margin-top: 5px;
      margin-left: -14px;
    }
    && > .menu .item {
      font-size: 15px;
      line-height: 20px;
      font-weight: 400;
      padding-top: 8px !important;
      padding-bottom: 8px !important;
    }
    && > .menu .item:hover,
    && > .menu .item.selected:hover {
      background: ${globals.MOON_100};
    }
    && > .menu .item.selected {
      background: transparent;
    }

    &.active svg {
      transform: rotate(180deg);
    }
  }
`;
ConfigFieldModifiedDropdown.displayName = 'S.ConfigFieldModifiedDropdown';

const IconDown = styled(IconDownUnstyled)`
  width: 18px;
  height: 18px;
`;
IconDown.displayName = 'S.IconDown';

const ConfigDimMenuButton = styled(IconButton).attrs({small: true})`
  margin-left: 4px;
  padding: 3px;
`;
ConfigDimMenuButton.displayName = 'S.ConfigDimMenuButton';
