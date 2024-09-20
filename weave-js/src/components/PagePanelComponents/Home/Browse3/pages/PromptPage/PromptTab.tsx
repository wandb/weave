import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import Accordion from '@mui/material/Accordion';
import AccordionDetails from '@mui/material/AccordionDetails';
import AccordionSummary from '@mui/material/AccordionSummary';
import Typography from '@mui/material/Typography';
import classNames from 'classnames';
import React from 'react';

import {LoadingDots} from '../../../../../LoadingDots';
import {Tailwind} from '../../../../../Tailwind';
import {usePrompt} from './hooks';
import {MessageList} from './MessageList';
import {PlaceholdersPanel} from './PlaceholdersPanel';
import {Data} from './types';

type PromptTabProps = {
  entity: string;
  project: string;
  data: Data;
};

export const PromptTab = ({entity, project, data}: PromptTabProps) => {
  const {loading, prompt} = usePrompt(entity, project, data);
  if (loading) {
    return <LoadingDots />;
  }
  if (!prompt) {
    return null;
  }

  const hasPlaceholders = prompt.placeholders.length > 0;

  return (
    <Tailwind>
      <div className="flex flex-col sm:flex-row">
        {hasPlaceholders && (
          <div className="w-full sm:order-2 sm:w-1/4 sm:pl-4">
            <Accordion defaultExpanded>
              <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                <Typography>Placeholders</Typography>
              </AccordionSummary>
              <AccordionDetails>
                <PlaceholdersPanel placeholders={prompt.placeholders} />
              </AccordionDetails>
            </Accordion>
          </div>
        )}
        <div
          className={classNames(
            'mt-4 w-full',
            hasPlaceholders ? 'sm:order-1 sm:mt-0 sm:w-3/4 sm:pr-4' : ''
          )}>
          <MessageList messages={prompt.messages} />
        </div>
      </div>
    </Tailwind>
  );
};
