import {Button} from '@wandb/weave/components/Button';
import classNames from 'classnames';
import React, {Dispatch, SetStateAction} from 'react';

type ShowMoreButtonProps = {
  isShowingMore: boolean;
  setIsShowingMore: Dispatch<SetStateAction<boolean>>;
  isUser?: boolean;
  isSystemPrompt?: boolean;
};

export const ShowMoreButton = ({
  isShowingMore,
  setIsShowingMore,
  isUser,
  isSystemPrompt,
}: ShowMoreButtonProps) => {
  return (
    <div
      className={classNames('flex w-full items-center justify-center', {
        'pt-[4px]': isShowingMore,
        [`absolute z-[1] mt-[-32px] rounded-b-xl bg-gradient-to-t from-70% pb-[4px] pt-[16px] 
          ${
            isUser
              ? 'from-[#f4fbe8]'
              : isSystemPrompt
              ? 'from-[#f8f8f8]'
              : 'from-white'
          } 
          to-transparent`]: !isShowingMore,
      })}>
      <Button
        variant="ghost"
        size="small"
        endIcon={isShowingMore ? 'chevron-up' : 'chevron-down'}
        onClick={() => setIsShowingMore(!isShowingMore)}>
        {isShowingMore ? 'Show less' : 'Show more'}
      </Button>
    </div>
  );
};
