import {Select} from '@wandb/weave/components/Form/Select';
import {TextArea} from '@wandb/weave/components/Form/TextArea';
import {TextField} from '@wandb/weave/components/Form/TextField';
import {Icon, IconName} from '@wandb/weave/components/Icon';
import React from 'react';

import {SECONDARY_BACKGROUND_COLOR} from './constants';

// Common styles for consistent UI
const UPPERCASE_LABEL_STYLE: React.CSSProperties = {
  fontSize: '12px',
  fontWeight: 600,
  color: '#666',
  textTransform: 'uppercase',
  letterSpacing: '0.5px',
};

export const LoadingSelect: typeof Select = props => {
  return <Select isDisabled placeholder="Loading..." {...props} />;
};

const FieldLabel: React.FC<{
  label: string;
  icon?: IconName;
  required?: boolean;
}> = ({label, icon, required}) => {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '4px',
        marginBottom: '8px',
        fontWeight: 600,
        fontSize: '14px',
      }}>
      {icon && <Icon name={icon} size="small" />}
      <span>{label}</span>
      {required && <span style={{color: '#ef4444'}}>*</span>}
    </div>
  );
};

const ValidationMessage: React.FC<{
  message: string;
  type: 'error' | 'warning' | 'info';
}> = ({message, type}) => {
  const colors = {
    error: '#ef4444',
    warning: '#f59e0b',
    info: '#6b7280',
  };

  const icons: Record<string, IconName> = {
    error: 'failed',
    warning: 'warning',
    info: 'info',
  };

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: '4px',
        marginTop: '4px',
        fontSize: '12px',
        color: colors[type],
      }}>
      <Icon name={icons[type]} size="small" />
      <span>{message}</span>
    </div>
  );
};

const Instructions: React.FC<{instructions: string}> = ({instructions}) => {
  return (
    <div
      style={{
        marginTop: '4px',
        fontSize: '12px',
        color: '#6b7280',
      }}>
      {instructions}
    </div>
  );
};

export const LabeledTextField: React.FC<{
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  icon?: IconName;
  required?: boolean;
  error?: string;
  warning?: string;
  instructions?: string;
  disabled?: boolean;
  onBlur?: () => void;
}> = ({
  label,
  value,
  onChange,
  placeholder,
  icon,
  required,
  error,
  warning,
  instructions,
  disabled,
  onBlur,
}) => {
  return (
    <div style={{display: 'flex', flexDirection: 'column'}}>
      <FieldLabel label={label} icon={icon} required={required} />
      <TextField
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        disabled={disabled}
        errorState={!!error}
        onBlur={onBlur}
      />
      {error && <ValidationMessage message={error} type="error" />}
      {!error && warning && (
        <ValidationMessage message={warning} type="warning" />
      )}
      {!error && !warning && instructions && (
        <Instructions instructions={instructions} />
      )}
    </div>
  );
};

export const LabeledTextArea: React.FC<{
  label: string;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
  placeholder?: string;
  icon?: IconName;
  required?: boolean;
  error?: string;
  warning?: string;
  instructions?: string;
  disabled?: boolean;
  rows?: number;
  onBlur?: () => void;
}> = ({
  label,
  value,
  onChange,
  placeholder,
  icon,
  required,
  error,
  warning,
  instructions,
  disabled,
  rows = 3,
  onBlur,
}) => {
  return (
    <div style={{display: 'flex', flexDirection: 'column'}}>
      <FieldLabel label={label} icon={icon} required={required} />
      <TextArea
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        disabled={disabled}
        rows={rows}
        style={{
          borderColor: error ? '#ef4444' : undefined,
        }}
        onBlur={onBlur}
      />
      {error && <ValidationMessage message={error} type="error" />}
      {!error && warning && (
        <ValidationMessage message={warning} type="warning" />
      )}
      {!error && !warning && instructions && (
        <Instructions instructions={instructions} />
      )}
    </div>
  );
};

export const PickerContainer: React.FC<{
  title: string;
  children: React.ReactNode;
  style?: React.CSSProperties;
}> = ({title, children, style}) => {
  return (
    <div
      style={{
        padding: '12px',
        backgroundColor: SECONDARY_BACKGROUND_COLOR,
        borderRadius: '4px',
        ...style,
      }}>
      <div
        style={{
          ...UPPERCASE_LABEL_STYLE,
          marginBottom: '8px',
        }}>
        {title}
      </div>
      {children}
    </div>
  );
};
