import {Box} from '@mui/material';
import {
  MOON_100,
  MOON_200,
  MOON_800,
  MOON_900,
  OBLIVION,
  TEAL_500,
} from '@wandb/weave/common/css/color.styles';
import {hexToRGB} from '@wandb/weave/common/css/utils';
import {Icon} from '@wandb/weave/components/Icon';
import {Tooltip} from '@wandb/weave/components/Tooltip';
import React, {useEffect, useRef, useState} from 'react';
import ReactDOM from 'react-dom';
import {components, OptionProps} from 'react-select';

import {Link} from '../../common/Links';
import {LLMMaxTokensKey} from '../llmMaxTokens';

export interface ProviderOption {
  label: string | React.ReactNode;
  value: string;
  llms: Array<{
    label: string;
    value: LLMMaxTokensKey;
    max_tokens: number;
  }>;
  isDisabled?: boolean;
}

export interface CustomOptionProps extends OptionProps<ProviderOption, false> {
  onChange: (value: LLMMaxTokensKey, maxTokens: number) => void;
  entity: string;
  project: string;
  isAdmin?: boolean;
}

export const DisabledProviderTooltip: React.FC<{
  children: React.ReactNode;
  entity: string;
  isAdmin?: boolean;
}> = ({children, entity, isAdmin = false}) => {
  return (
    <Tooltip
      trigger={children}
      aria-label="Provider configuration status"
      content={
        <Box
          sx={{
            backgroundColor: MOON_900,
            color: 'white',
            fontSize: '14px',
            fontWeight: 400,
            borderRadius: '4px',
          }}>
          <div>This provider is not configured.</div>
          <div>
            Check{' '}
            {isAdmin ? (
              <Link
                to={`/${entity}/settings`}
                target="_blank"
                aria-label="Go to team settings to configure missing secrets"
                rel="noopener noreferrer"
                style={{
                  color: TEAL_500,
                  textDecoration: 'none',
                }}
                className="hover:opacity-80">
                missing secrets
              </Link>
            ) : (
              'missing secrets'
            )}{' '}
            to enable it.
          </div>
        </Box>
      }
    />
  );
};

const SubMenu = ({
  llms,
  onChange,
  position,
  onSelect,
}: {
  llms: Array<{label: string; value: LLMMaxTokensKey; max_tokens: number}>;
  onChange: (value: LLMMaxTokensKey, maxTokens: number) => void;
  position: {top: number; left: number};
  onSelect: () => void;
}) => {
  return ReactDOM.createPortal(
    <Box
      sx={{
        position: 'fixed',
        left: position.left - 4,
        top: position.top - 6,
        backgroundColor: 'white',
        boxShadow: '0 2px 8px ' + hexToRGB(OBLIVION, 0.15),
        borderRadius: '4px',
        width: '300px',
        maxHeight: '400px',
        overflowY: 'auto',
        border: '1px solid ' + hexToRGB(OBLIVION, 0.1),
        p: '6px',
      }}>
      {llms.map((llm, index) => (
        <Box
          key={llm.value}
          onClick={e => {
            e.preventDefault();
            e.stopPropagation();
            onChange(llm.value, llm.max_tokens);
            onSelect();
          }}
          sx={{
            width: '100%',
            wordBreak: 'break-all',
            wordWrap: 'break-word',
            whiteSpace: 'normal',
            p: '6px',
            cursor: 'pointer',
            borderRadius: '4px',
            '&:hover': {
              backgroundColor: hexToRGB(OBLIVION, 0.04),
            },
          }}>
          {llm.label}
        </Box>
      ))}
    </Box>,
    document.body
  );
};

const SubMenuOption = ({
  children,
  onChange,
  entity,
  project,
  isAdmin,
  ...props
}: CustomOptionProps) => {
  const [isHovered, setIsHovered] = useState(false);
  const [position, setPosition] = useState({top: 0, left: 0});
  const optionRef = useRef<HTMLDivElement>(null);
  const {llms, isDisabled} = props.data;

  useEffect(() => {
    if (isHovered && optionRef.current) {
      const rect = optionRef.current.getBoundingClientRect();
      setPosition({
        top: rect.top,
        left: rect.right + 4,
      });
    }
  }, [isHovered]);

  const optionContent = React.useMemo(
    () => (
      <Box
        ref={optionRef}
        onMouseEnter={() => !isDisabled && setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        sx={{
          position: 'relative',
          width: '100%',
          opacity: isDisabled ? 0.5 : 1,
        }}>
        <Box sx={{position: 'relative', zIndex: 1}}>
          <components.Option {...props}>
            <Box sx={{display: 'flex', justifyContent: 'space-between'}}>
              <Box
                sx={{
                  wordBreak: 'break-all',
                  wordWrap: 'break-word',
                  whiteSpace: 'normal',
                  width: '90%',
                }}>
                {children}
              </Box>
              {llms.length > 0 && <Icon name="chevron-next" color="moon_500" />}
            </Box>
          </components.Option>
        </Box>
        {isHovered && llms.length > 0 && (
          <SubMenu
            llms={llms}
            onChange={onChange}
            position={position}
            onSelect={() => {
              props.selectProps.onInputChange?.('', {
                action: 'set-value',
                prevInputValue: props.selectProps.inputValue,
              });
              props.selectProps.onMenuClose?.();
            }}
          />
        )}
      </Box>
    ),
    [children, isDisabled, isHovered, llms, onChange, position, props]
  );

  if (props.data.value === 'divider') {
    return (
      <Box
        sx={{
          borderBottom: `1px solid ${MOON_200}`,
          mb: 1,
        }}
      />
    );
  }

  return isDisabled ? (
    <DisabledProviderTooltip entity={entity} isAdmin={isAdmin}>
      {optionContent}
    </DisabledProviderTooltip>
  ) : (
    optionContent
  );
};

export const CustomOption = ({
  children,
  onChange,
  entity,
  project,
  isAdmin,
  ...props
}: CustomOptionProps) => {
  const {inputValue} = props.selectProps;

  // If searching, show nested structure
  if (inputValue) {
    const {llms, isDisabled} = props.data;
    if (isDisabled) {
      return null;
    }

    const filteredLLMs = llms.filter(llm =>
      llm.value.toLowerCase().includes(inputValue.toLowerCase())
    );

    return (
      <Box>
        <Box
          sx={{
            padding: '4px 12px 0',
            color: MOON_800,
            fontWeight: 600,
            cursor: 'default',
            borderRadius: '4px',
            display: 'flex',
            alignItems: 'center',
            wordBreak: 'break-all',
            wordWrap: 'break-word',
            whiteSpace: 'normal',
          }}>
          {props.data.label}
        </Box>
        <Box
          sx={{
            px: '4px',
            wordBreak: 'break-all',
            wordWrap: 'break-word',
            whiteSpace: 'normal',
          }}>
          {filteredLLMs.map(llm => (
            <Box
              key={llm.value}
              onClick={() => {
                onChange(llm.value as LLMMaxTokensKey, llm.max_tokens);
                props.selectProps.onInputChange?.('', {
                  action: 'set-value',
                  prevInputValue: props.selectProps.inputValue,
                });
                props.selectProps.onMenuClose?.();
              }}
              sx={{
                padding: '8px 12px',
                cursor: 'pointer',
                borderRadius: '4px',
                '&:hover': {
                  backgroundColor: MOON_100,
                },
              }}>
              {llm.label}
            </Box>
          ))}
        </Box>
      </Box>
    );
  }
  // If not searching, use the hover submenu
  return (
    <SubMenuOption
      {...props}
      onChange={onChange}
      entity={entity}
      project={project}
      isAdmin={isAdmin}>
      {children}
    </SubMenuOption>
  );
};

export const dividerOption: ProviderOption = {
  label: '',
  value: 'divider',
  llms: [],
};

export const addProviderOption: ProviderOption = {
  label: (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 1,
      }}>
      <Icon name="add-new" />
      Add AI provider
    </Box>
  ),
  value: 'add-provider',
  llms: [],
};
