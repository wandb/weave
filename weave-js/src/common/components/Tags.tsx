import _ from 'lodash';
import React, {useState} from 'react';
import {Label} from 'semantic-ui-react';

import * as GQLTypes from '../types/graphql';
import {SingleLineText} from './elements/Text';
import * as S from './Tags.styles';

export enum TagType {
  TAG,
  ALIAS,
  PROTECTED_ALIAS,
}

interface TagProps {
  size?: 'large' | 'medium' | 'small';
  tag: GQLTypes.Tag;
  noun?: 'tag' | 'alias' | 'protected-alias';
  canDelete?: boolean;
  showColor?: boolean;

  onDelete?(e: React.MouseEvent<HTMLElement>): void;
  onClick?(): void;
}

function nounToTagType(noun: string): TagType {
  switch (noun) {
    case 'tag':
      return TagType.TAG;
    case 'alias':
      return TagType.ALIAS;
    case 'protected-alias':
      return TagType.PROTECTED_ALIAS;
    default:
      return TagType.TAG;
  }
}

function colorIndexToName(showColor: boolean, index?: number): string {
  if (!showColor) {
    return 'tag-lightGray';
  }
  switch (index) {
    case TagType.TAG:
      return 'tag-teal-light';
    case TagType.ALIAS:
      return 'tag-sienna-light';
    case TagType.PROTECTED_ALIAS:
      return 'tag-purple';
    default:
      return 'tag-lightGray';
  }
}

export const Tag: React.FC<TagProps> = React.memo(
  ({size: propsSize, tag, noun, canDelete, showColor, onDelete, onClick}) => {
    const [showDeleteAlert, setShowDeleteAlert] = useState(false);
    const size = propsSize || 'large';
    noun = noun ?? 'tag';
    canDelete = canDelete ?? true;
    showColor = showColor ?? true;

    // As per new design guidelines, colors for tags and aliases are no longer random
    // Since they've been fixed based on tag type (aka `noun`), the color assignment here will ignore
    // the database color index. This can be modified in the future if the design decision changes
    // based on user feedback
    const colorName = colorIndexToName(showColor, nounToTagType(noun));
    return (
      <Label
        style={{marginLeft: '2px', maxWidth: '220px'}}
        className={
          showDeleteAlert
            ? `run-tag ${size} tag-red-alert`
            : `run-tag ${size} ${colorName}`
        }
        key={tag.name}
        onClick={onClick}>
        <S.Icon
          name={noun === 'tag' ? 'tag-latest' : 'email-at'}
          size={size}
          $pos="left"
        />
        <SingleLineText alignSelf={'center'}>{tag.name}</SingleLineText>
        {canDelete && onDelete && (
          <S.Icon
            className="delete-tag"
            name="close-latest"
            size={size}
            onClick={(e: React.MouseEvent<HTMLElement>) => {
              e.stopPropagation();
              onDelete(e);
            }}
            onMouseOver={() => setShowDeleteAlert(true)}
            onMouseOut={() => setShowDeleteAlert(false)}
            $pos="right"
            $opacity={0.6}
            $cursor="pointer"
          />
        )}
      </Label>
    );
  }
);

interface TagsProps {
  size?: 'medium' | 'small';
  tags: GQLTypes.Tag[];
  enableDelete?: boolean;
  noun?: 'tag' | 'alias';

  deleteTag?(tag: GQLTypes.Tag): void;
  onClick?(tag: string): void;
}

export const Tags: React.FC<TagsProps> = React.memo(
  ({size, tags, enableDelete, noun, deleteTag, onClick}) => {
    return (
      <span className="run-tags">
        {_.sortBy(tags, 'name').map(tag => (
          <Tag
            key={tag.name}
            tag={tag}
            size={size}
            onDelete={
              enableDelete && deleteTag
                ? e => {
                    if (deleteTag) {
                      e.stopPropagation();
                      deleteTag(tag);
                    }
                  }
                : undefined
            }
            onClick={() => onClick?.(tag.name)}
            noun={noun}
          />
        ))}
      </span>
    );
  }
);
