import React, {PropsWithChildren} from 'react';

import {TooltipTrigger} from '../Tooltip';

export const chainColor = '#F59B1414';
export const chainTextColor = '#C77905';
export const toolColor = '#9CC74818';
export const toolTextColor = '#669432';
export const agentColor = '#0096AD14';
export const agentTextColor = '#0096AD';
export const llmColor = '#CD5BF016';
export const llmTextColor = '#9E36C2';
export const promptColor = '#9278EB18';
export const promptTextColor = '#775CD1';

export const MinimalTooltip: React.FC<
  PropsWithChildren<{text: string; lengthLimit?: number}>
> = ({children, text, lengthLimit}) => {
  const limit = lengthLimit ?? 100;
  if (text.length < limit) {
    return <>{children}</>;
  }
  return (
    <TooltipTrigger copyableContent={text} content={<pre>{text}</pre>}>
      {children}
    </TooltipTrigger>
  );
};
