import classNames from 'classnames';
import React from 'react';

import {Tailwind} from '../../../../../../Tailwind';
import {MessageList} from '../../ChatView/MessageList';

type Data = Record<string, any>;

type TabPromptProps = {
  entity: string;
  project: string;
  data: Data;
};

export const TabPrompt = ({entity, project, data}: TabPromptProps) => {
  return (
    <Tailwind>
      <div className="flex flex-col sm:flex-row">
        <div className={classNames('mt-4 w-full')}>
          <MessageList messages={data.data} />
        </div>
      </div>
    </Tailwind>
  );
};
