import classNames from 'classnames';
import React from 'react';

import * as Colors from '../../../../../common/css/color.styles';
import {Icon} from '../../../../Icon';

type ValueInputBooleanProps = {
  value: string | boolean | undefined;
  onSetValue: (value: string) => void;
};

const CLASS_NAMES_BUTTON = classNames(
  'night-aware cursor-pointer',
  "inline-flex items-center justify-center whitespace-nowrap rounded border-none font-['Source_Sans_Pro'] font-semibold",
  'disabled:pointer-events-none disabled:opacity-35',
  'focus-visible:outline focus-visible:outline-[2px] focus-visible:outline-teal-500',
  'gap-6 px-6 py-3 text-sm leading-[18px]',
  '[&_svg]:h-16 [&_svg]:w-16',
  'bg-oblivion/[0.05] dark:bg-moonbeam/[0.05]',
  'text-moon-800 dark:text-moon-200',
  'hover:bg-teal-300/[0.48] hover:text-teal-600 dark:hover:bg-teal-700/[0.48] dark:hover:text-teal-400'
);

export const ValueInputBoolean = ({
  value,
  onSetValue,
}: ValueInputBooleanProps) => {
  const isTrue = value === 'true' || value === true;
  const isFalse = value === 'false' || value === false;
  const classNamesTrue = classNames(CLASS_NAMES_BUTTON, {
    'bg-teal-300/[0.48] text-teal-600 dark:bg-teal-700/[0.48] dark:text-teal-400':
      isTrue,
  });
  const classNamesFalse = classNames(CLASS_NAMES_BUTTON, {
    'bg-teal-300/[0.48] text-teal-600 dark:bg-teal-700/[0.48] dark:text-teal-400':
      isFalse,
  });

  // TODO: Maybe clicking on the current value should deselect?

  return (
    <div className="flex items-center gap-4">
      <div className={classNamesTrue} onClick={() => onSetValue('true')}>
        <Icon color={Colors.GREEN_600} name="checkmark" /> True
      </div>
      <div className={classNamesFalse} onClick={() => onSetValue('false')}>
        <Icon color={Colors.RED_600} name="close" /> False
      </div>
    </div>
  );
};
