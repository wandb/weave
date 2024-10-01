/**
 * This component displays a code snippet that can be copied to the clipboard.
 */

import classNames from 'classnames';
import copyToClipboard from 'copy-to-clipboard';
import Prism from 'prismjs';
import React, {CSSProperties, useCallback, useEffect, useRef} from 'react';
import styled from 'styled-components';

import {toast} from '../common/components/elements/Toast';
import {MOON_150, MOON_250, MOON_950} from '../common/css/color.styles';
import {hexToRGB} from '../common/css/utils';
import {Icon, IconName} from './Icon';
import {Tooltip} from './Tooltip';

type CopyableTextProps = {
  text: string;

  // The text to copy to the clipboard. If not provided, `text` will be used.
  copyText?: string;

  // If specified, passed to Prism for syntax highlighting.
  language?: string;

  tooltipText?: string;
  toastText?: string;
  icon?: IconName;
  disabled?: boolean;
  onClick?(): void;
};

// Background color picked to match alert
const Wrapper = styled.div<{isMultiline?: boolean}>`
  background-color: ${hexToRGB(MOON_950, 0.04)};
  position: relative;
  align-items: ${props => (props.isMultiline ? 'flex-start' : 'center')};
  cursor: pointer;
  padding: 8px;
  border-radius: 8px;
  margin-top: 8px;
  &:hover {
    background-color: ${MOON_150};
    & > .button_copy {
      display: flex;
    }
  }
`;
Wrapper.displayName = 'S.Wrapper';

const IconCell = styled.div`
  position: absolute;
  top: 4px;
  right: 4px;
  flex: 0 0 auto;
  align-items: center;
  display: none;
  align-items: center;
  background-color: ${MOON_250};
  padding: 4px 8px;
  border-radius: 8px;
  font-weight: 600;
`;
IconCell.displayName = 'S.IconCell';

const Text = styled.code`
  white-space: pre-line;
  overflow: auto;
  text-overflow: ellipsis;
`;
Text.displayName = 'S.Text';

export const CopyableText = ({
  text,
  copyText,
  language,
  tooltipText = 'Click to copy to clipboard',
  toastText = 'Copied to clipboard',
  icon,
  disabled,
  onClick,
}: CopyableTextProps) => {
  const ref = useRef<HTMLElement>(null);

  const copy = useCallback(() => {
    copyToClipboard(copyText ?? text);
    toast(toastText);
  }, [text, copyText, toastText]);

  const style: CSSProperties = {marginRight: 8};
  const isMultiline = text.includes('\n');
  if (isMultiline) {
    style.marginTop = 4;
  }

  useEffect(() => {
    Prism.highlightElement(ref.current!);
  });

  const trigger = (
    <Wrapper
      isMultiline={isMultiline}
      onClick={e => {
        e.stopPropagation();
        if (disabled) {
          return;
        }
        copy();
        onClick?.();
      }}>
      <IconCell className="button_copy">
        <Icon name={icon ?? 'copy'} width={16} height={16} style={style} />
        Copy
      </IconCell>
      <Text
        ref={ref}
        className={classNames(
          "whitespace-pre-wrap font-['Inconsolata'] text-sm",
          language ? `language-${language}` : ''
        )}>
        {text}
      </Text>
    </Wrapper>
  );
  return <Tooltip content={tooltipText} trigger={trigger} />;
};
