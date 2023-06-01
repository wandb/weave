import * as React from 'react';
import {RenderLeafProps} from 'slate-react';

// Leaf component passed to (Slate) Editable's `renderLeaf`
export const Leaf = ({leaf, attributes, children}: RenderLeafProps) => {
  // We apply any marks on leaf as class names
  const classes: string[] = Object.keys(leaf).reduce<string[]>(
    (result, key) => {
      if (key === 'text') {
        return result;
      }

      if (['+', '-', '/', '*', '!', '%'].includes(key)) {
        return result.concat('operator');
      }

      if (['true', 'false'].includes(key)) {
        return result.concat('boolean');
      }

      return result.concat(key);
    },
    []
  );

  // Uniques only
  const uniqueClasses = Array.from(new Set(classes));
  return (
    <span
      {...attributes}
      className={classes != null ? uniqueClasses.join(' ') : undefined}>
      {children}
    </span>
  );
};
