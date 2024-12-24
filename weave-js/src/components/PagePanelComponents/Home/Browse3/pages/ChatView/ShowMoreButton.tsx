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
        'flex w-full items-center justify-center',
        {
          'pt-[4px]': isShowingMore,
          [`absolute mt-[-32px] pt-[16px] pb-[4px] from-70% z-[1] rounded-b-xl bg-gradient-to-t ${
            isUser ? 'from-[#f4fbe8]' : 'from-white'
          } to-transparent`]: !isShowingMore,
        }
      )}>
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
