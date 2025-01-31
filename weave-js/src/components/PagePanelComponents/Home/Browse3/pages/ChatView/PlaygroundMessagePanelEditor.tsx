import {Button} from '@wandb/weave/components/Button';
import classNames from 'classnames';
import _ from 'lodash';
import React, {useEffect, useMemo, useState} from 'react';

import {usePlaygroundContext} from '../PlaygroundPage/PlaygroundContext';
import {StyledTextArea} from '../../StyledTextarea';
import {Message} from './types';

type PlaygroundMessagePanelEditorProps = {
  editorHeight: number;
  isNested: boolean;
  pendingToolResponseId?: string;
  message: Message;
  index: number;
  choiceIndex?: number;
  setEditorHeight: (height: number | null) => void;
};

export const PlaygroundMessagePanelEditor: React.FC<
  PlaygroundMessagePanelEditorProps
> = ({
  index,
  choiceIndex,
  setEditorHeight,
  editorHeight,
  isNested,
  pendingToolResponseId,
  message,
}) => {
  const {sendMessage, editMessage, editChoice} = usePlaygroundContext();

  const initialContent = useMemo(
    () =>
      _.isString(message.content)
        ? message.content
        : message.content?.join('') ?? '',
    [message.content]
  );

  const [editedContent, setEditedContent] = useState(initialContent);

  useEffect(() => {
    setEditedContent(initialContent);
  }, [initialContent]);

  const handleSave = () => {
    if (choiceIndex !== undefined) {
      editChoice?.(choiceIndex, {
        ...message,
        content: editedContent,
      });
    } else {
      editMessage?.(index, {
        ...message,
        content: editedContent,
      });
    }
    setEditorHeight(null);
  };

  const handleCancel = () => {
    setEditedContent(initialContent);
    setEditorHeight(null);
  };

  return (
    <div
      className={classNames(
        'w-full pt-[6px]',
        isNested ? 'px-[4px]' : 'px-[16px]'
      )}>
      <StyledTextArea
        value={editedContent}
        onChange={e => setEditedContent(e.target.value)}
        startHeight={320}
      />
      {/* 6px vs. 8px to make up for extra padding from textarea field */}
      <div className="z-100 mt-[6px] flex justify-end gap-[8px]">
        <Button variant="ghost" size="medium" onClick={handleCancel}>
          Cancel
        </Button>
        <Button
          variant="primary"
          size="medium"
          onClick={
            pendingToolResponseId
              ? () =>
                  sendMessage?.(
                    'tool',
                    editedContent ?? '',
                    pendingToolResponseId
                  )
              : handleSave
          }>
          Save
        </Button>
      </div>
    </div>
  );
};
