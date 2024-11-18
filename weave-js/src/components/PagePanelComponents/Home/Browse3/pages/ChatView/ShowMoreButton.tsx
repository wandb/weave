import {Button} from '@wandb/weave/components/Button';
import classNames from 'classnames';
import React, {Dispatch, SetStateAction} from 'react';

type ShowMoreButtonProps = {
  isShowingMore: boolean;
  setIsShowingMore: Dispatch<SetStateAction<boolean>>;
  isUser?: boolean;
};
export const ShowMoreButton = ({
  isShowingMore,
  setIsShowingMore,
  isUser,
}: ShowMoreButtonProps) => {
  return (
    <div
      className={classNames(
        'absolute bottom-0 left-0 flex w-full items-center justify-center pb-4 pt-32',
        {
          [`from-34% rounded-b-xl bg-gradient-to-t ${
            isUser ? 'from-cactus-300/[0.24]' : 'from-moon-100'
          } to-transparent`]: !isShowingMore,
        }
      )}>
      <Button
        className="z-10"
        variant="ghost"
        endIcon={isShowingMore ? 'chevron-up' : 'chevron-down'}
        onClick={() => setIsShowingMore(!isShowingMore)}>
        {isShowingMore ? 'Show less' : 'Show more'}
      </Button>
    </div>
  );
};
