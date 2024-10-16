import React from 'react';

type HorizontalRuleWithLabelProps = {
  label: string;
};

export const HorizontalRuleWithLabel = ({
  label,
}: HorizontalRuleWithLabelProps) => {
  return (
    <div className="mb-12 flex w-full items-center">
      <hr className="border-t-1 flex-grow border-moon-350" />
      <span className="mx-16 whitespace-nowrap text-xs leading-loose text-moon-500">
        {label}
      </span>
      <hr className="border-t-1 flex-grow border-moon-350" />
    </div>
  );
};
