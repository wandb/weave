import * as globals from '@wandb/weave/common/css/globals.styles';
import {Link, LinkProps} from '@wandb/weave/common/util/links';
import React from 'react';
import {Button, StrictButtonProps} from 'semantic-ui-react';
import styled, {css} from 'styled-components';

type WBButtonVariant = `ghost` | `confirm` | `plain`;
type WBButtonSize = `icon` | `small` | `medium`;

type WBButtonBaseProps = {
  variant?: WBButtonVariant;
  size?: WBButtonSize;
};

type WBButtonProps = WBButtonBaseProps &
  Omit<StrictButtonProps, keyof WBButtonBaseProps>;

export const WBButton: React.FC<WBButtonProps> = React.memo(
  ({...passThroughProps}) => {
    return <ButtonStyled {...passThroughProps} />;
  }
);

type WBButtonLinkProps = WBButtonBaseProps & LinkProps;

export const WBButtonLink: React.FC<WBButtonLinkProps> = React.memo(
  ({...passThroughProps}) => {
    return <ButtonLinkStyled {...passThroughProps} />;
  }
);

const buttonStyles = css<WBButtonBaseProps>`
  &&& {
    display: inline-flex;
    align-items: center;

    line-height: 1.5em;
    font-weight: 600;
    border: none;
    border-radius: 0.25rem;
    margin: 0;

    transition: background-color 0.3s, color 0.3s;

    ${({variant = `ghost`}) =>
      variant === `ghost`
        ? css`
            &,
            &:active,
            &:focus {
              color: ${globals.TEXT_PRIMARY_COLOR};
              background-color: transparent;
            }
            &:hover {
              color: ${globals.TEAL};
              background-color: ${globals.TEAL_TRANSPARENT_2};
            }
          `
        : variant === `confirm`
        ? css`
            &,
            &:active,
            &:focus {
              color: ${globals.white};
              background-color: ${globals.TEAL_LIGHT};
            }
            &:hover {
              background-color: ${globals.TEAL_LIGHT_2};
            }
          `
        : variant === `plain` &&
          css`
            &,
            &:active,
            &:focus {
              color: ${globals.TEXT_PRIMARY_COLOR};
              background-color: ${globals.GRAY_TRANSPARENT};
            }
            &:hover {
              color: ${globals.TEAL};
              background-color: ${globals.TEAL_TRANSPARENT_2};
            }
          `}

    ${({size = `small`}) =>
      size === `icon`
        ? css`
            padding: 4px;
          `
        : size === `small`
        ? css`
            padding: 4px 10px;
          `
        : size === `medium` &&
          css`
            padding: 8px 16px;
          `}
  }
`;

const ButtonStyled = styled(Button)`
  ${buttonStyles}
`;

const ButtonLinkStyled = styled(Link)`
  ${buttonStyles}
`;
