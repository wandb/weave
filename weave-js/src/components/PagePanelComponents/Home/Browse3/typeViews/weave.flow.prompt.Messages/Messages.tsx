import React from 'react';

import {CustomWeaveTypePayload} from '../customWeaveType.types';

type MessagesTypePayload = CustomWeaveTypePayload<
  'weave.flow.prompt.Messages',
  {'image.png': string}
>;

export const Messages: React.FC<{
  entity: string;
  project: string;
  data: MessagesTypePayload;
}> = props => {
  return <div>Messages</div>;
};
