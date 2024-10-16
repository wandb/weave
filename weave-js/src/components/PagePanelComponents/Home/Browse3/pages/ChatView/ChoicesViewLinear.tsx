import React from 'react';

import {Button} from '../../../../../Button';
import {ChoiceView} from './ChoiceView';
import {Choice, ChoicesMode} from './types';

type ChoicesViewLinearProps = {
  choices: Choice[];
  isStructuredOutput?: boolean;
  setMode: React.Dispatch<React.SetStateAction<ChoicesMode>>;
};

export const ChoicesViewLinear = ({
  choices,
  isStructuredOutput,
  setMode,
}: ChoicesViewLinearProps) => {
  return (
    <div className="flex flex-col gap-36">
      {choices.map(c => (
        <div>
          <div className="mt-8 flex items-center">
            <div
              id={`choice-${c.index}`}
              className="flex flex-auto items-center gap-4 text-xs">
              {c.index !== 0 && (
                <Button
                  size="small"
                  variant="quiet"
                  icon="chevron-back"
                  onClick={() => {
                    const prevChoice = document.getElementById(
                      `choice-${c.index - 1}`
                    );
                    prevChoice?.scrollIntoView({behavior: 'smooth'});
                  }}
                />
              )}
              <span>
                Choice {c.index + 1} of {choices.length}
              </span>
              {c.index !== choices.length - 1 && (
                <Button
                  size="small"
                  variant="quiet"
                  icon="chevron-next"
                  onClick={() => {
                    const nextChoice = document.getElementById(
                      `choice-${c.index + 1}`
                    );
                    nextChoice?.scrollIntoView({behavior: 'smooth'});
                  }}
                />
              )}
            </div>
            <Button
              size="small"
              variant="quiet"
              icon="collapse"
              onClick={() => setMode('carousel')}
              tooltip="Switch to carousel view"
            />
          </div>
          <ChoiceView
            key={c.index}
            choice={c}
            isStructuredOutput={isStructuredOutput}
          />
        </div>
      ))}
    </div>
  );
};
