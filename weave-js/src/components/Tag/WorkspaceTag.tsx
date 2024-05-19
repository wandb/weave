import React from 'react';

import {Tag as TagType} from '../../common/types/graphql';
import {RemoveAction} from './RemoveAction';
import {RemovableTag, Tag} from './Tag';
import {getTagContrastColor} from './utils';

type WorkspaceTagProps = React.HTMLAttributes<HTMLDivElement> & {
  tag: TagType;
  onRemoveClick?: Record<string, any>;
};

export const WorkspaceTag = React.forwardRef<HTMLDivElement, WorkspaceTagProps>(
  ({tag, onRemoveClick, ...htmlAttributes}, ref) => {
    return (
      <div ref={ref} data-test="run-tag" {...htmlAttributes}>
        {onRemoveClick == null ? (
          <Tag label={tag.name} color={getTagContrastColor(tag.colorIndex)} />
        ) : (
          <RemovableTag
            label={tag.name}
            color={getTagContrastColor(tag.colorIndex)}
            removeAction={<RemoveAction onClick={onRemoveClick} />}
          />
        )}
      </div>
    );
  }
);
