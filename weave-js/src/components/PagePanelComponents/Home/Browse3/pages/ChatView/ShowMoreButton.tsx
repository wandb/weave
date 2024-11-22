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
        'mb-[-8px] flex w-full items-center justify-center pb-8',
        {
          [`from-34% rounded-b-xl bg-gradient-to-t ${
            isUser ? 'from-cactus-300/[0.32]' : 'from-moon-150'
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
