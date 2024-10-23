import React, {useEffect, useRef, useState} from 'react';

type ViewNameEditingProps = {
  value: string;

  onChanged: (value: string) => void;
  onExit: () => void;
};

export const ViewNameEditing = ({
  value,
  onChanged,
  onExit,
}: ViewNameEditingProps) => {
  const [activeValue, setActiveValue] = useState(value);
  const inputRef = useRef<HTMLInputElement>(null);

  // Select all of the text
  // TODO: Make this behavior optional?
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.select();
    }
  }, []);

  const onChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.currentTarget.value;
    setActiveValue(newValue);
  };
  const onBlur = () => {
    // TODO: Trim? Disallow whitespace only?
    if (activeValue !== value) {
      onChanged(activeValue);
    }
    onExit();
  };
  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Escape') {
      onExit();
    } else if (e.key === 'Enter') {
      onBlur();
    }
  };
  const placeholder = value;
  return (
    <div className="flex items-center gap-8">
      <input
        ref={inputRef}
        className="max-tracking-[0.1px] w-full focus-within:outline-2 focus-within:outline-teal-400 dark:focus-within:outline-teal-600"
        value={activeValue}
        placeholder={placeholder}
        onChange={onChange}
        onKeyDown={onKeyDown}
        onBlur={onBlur}
        autoFocus
      />
      <p className="rounded bg-moon-100 px-6 text-sm text-moon-500 ">Enter</p>
    </div>
  );

  //   onChange={e => {
  //     let newVal = e.currentTarget.value;
  //     if (this.props.type === 'url') {
  //       newVal = removeUrlProtocolPrefix(newVal);
  //     }
  //     this.updateValue(newVal);
  //   }}
  //   placeholder={this.props.placeholder}
  //   onKeyDown={this.onKeyDown}
  //   ref={this.inputRef}
  //   onBlur={this.stopEditing}
};
