import React, {FC, ReactElement} from 'react';
import {twMerge} from 'tailwind-merge';

import {Icon} from '../Icon';
import {
  TruncateByCharsProps,
  TruncateByCharsWithTooltip,
} from '../TruncateByCharsWithTooltip';
import {RemoveAction} from './RemoveAction';
import {useTagClasses} from './Tag';
import {TAG_DEFAULT_MAX_CHARS, TagColorName} from './utils';

export const DEFAULT_ALIAS_ICON = 'email-at';

export type AliasProps = TruncateByCharsProps & {
  label: string;
  color?: TagColorName;
  showIcon?: boolean;
};
export const Alias: FC<AliasProps> = ({
  label,
  color,
  showIcon = false,
  maxChars = TAG_DEFAULT_MAX_CHARS,
  truncatedPart,
  Wrapper,
}) => {
  const classes = useTagClasses({color, label});
  const truncationProps = {text: label, maxChars, truncatedPart, Wrapper};
  return (
    <TruncateByCharsWithTooltip {...truncationProps}>
      {({truncatedText}) => (
        <div
          className={twMerge(
            classes,
            'font-mono text-[13px]',
            showIcon ? 'pl-4 pr-6' : 'px-6'
          )}>
          {showIcon && (
            <Icon
              role="presentation"
              className="mr-4 h-14 w-14"
              name={DEFAULT_ALIAS_ICON}
            />
          )}
          <span>{truncatedText}</span>
        </div>
      )}
    </TruncateByCharsWithTooltip>
  );
};

export type RemovableAliasProps = TruncateByCharsProps & {
  label: string;
  removeAction: ReactElement<typeof RemoveAction>;
  color?: TagColorName;
  showIcon?: boolean;
};
export const RemovableAlias: FC<RemovableAliasProps> = ({
  label,
  removeAction,
  color,
  showIcon = false,
  maxChars = TAG_DEFAULT_MAX_CHARS,
  truncatedPart,
  Wrapper,
}) => {
  const classes = useTagClasses({color, label, isInteractive: true});
  const truncationProps = {text: label, maxChars, truncatedPart, Wrapper};
  return (
    <TruncateByCharsWithTooltip {...truncationProps}>
      {({truncatedText}) => (
        <div className={twMerge(classes, 'px-4 font-mono text-[13px]')}>
          {showIcon && (
            <Icon
              role="presentation"
              className="mr-4 h-14 w-14"
              name={DEFAULT_ALIAS_ICON}
            />
          )}
          <span>{truncatedText}</span>
          {removeAction}
        </div>
      )}
    </TruncateByCharsWithTooltip>
  );
};
