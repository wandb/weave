import {Box, Link, Typography} from '@mui/material';
import {TEAL_500, TEAL_600} from '@wandb/weave/common/css/color.styles';
import {Button} from '@wandb/weave/components/Button';
import {TextField} from '@wandb/weave/components/Form/TextField';
import {Icon} from '@wandb/weave/components/Icon';
import {Tooltip} from '@wandb/weave/components/Tooltip';
import React from 'react';

// Shared typography style
export const sharedTypographyStyle = {
  fontSize: '16px',
  fontFamily: 'Source Sans Pro',
};

// Header component
export const ProviderDrawerHeader: React.FC<{
  title: string;
  isFullscreen: boolean;
  onToggleFullscreen: () => void;
  onClose: () => void;
}> = ({title, isFullscreen, onToggleFullscreen, onClose}) => {
  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        pl: 2,
        pr: 1,
        height: '44px',
        minHeight: '44px',
        borderBottom: '1px solid',
        borderColor: 'divider',
      }}>
      <Typography
        variant="h6"
        sx={{...sharedTypographyStyle, fontSize: '20px', fontWeight: 600}}>
        {title}
      </Typography>
      <Box sx={{display: 'flex', gap: 1}}>
        <Button
          onClick={onToggleFullscreen}
          variant="ghost"
          icon={isFullscreen ? 'minimize-mode' : 'full-screen-mode-expand'}
          tooltip={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
        />
        <Button
          onClick={onClose}
          variant="ghost"
          icon="close"
          tooltip="Close"
        />
      </Box>
    </Box>
  );
};

// Headers component
export const HeadersInput: React.FC<{
  headers: Array<[string, string]>;
  onHeadersChange: (headers: Array<[string, string]>) => void;
}> = ({headers, onHeadersChange}) => {
  return (
    <Box>
      <Box
        sx={{
          mb: 1,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}>
        <Typography sx={{...sharedTypographyStyle, fontWeight: '600'}}>
          Headers
        </Typography>
        <Button
          variant="secondary"
          size="small"
          icon="add-new"
          onClick={() =>
            onHeadersChange(headers ? [...headers, ['', '']] : [['', '']])
          }>
          Add a header
        </Button>
      </Box>
      <Box sx={{display: 'flex', flexDirection: 'column', gap: 1}}>
        {headers?.map(([key, value], index) => (
          <Box key={index} sx={{display: 'flex', alignItems: 'center', gap: 1}}>
            <TextField
              placeholder="Enter header key..."
              value={key}
              onChange={val =>
                onHeadersChange(
                  headers.map(([k, v], i) => (i === index ? [val, v] : [k, v]))
                )
              }
            />
            <TextField
              placeholder="Enter header value..."
              value={value}
              onChange={val =>
                onHeadersChange(
                  headers.map(([k, v], i) => (i === index ? [k, val] : [k, v]))
                )
              }
            />
            <Button
              variant="ghost"
              icon="delete"
              onClick={() => {
                const newHeaders = [...headers];
                newHeaders.splice(index, 1);
                onHeadersChange(newHeaders);
              }}
            />
          </Box>
        ))}
      </Box>
    </Box>
  );
};

// Model component
export const ModelInput: React.FC<{
  model: string;
  maxToken: number;
  providerName: string;
  index: number;
  onModelChange: (value: string, index: number) => void;
  onMaxTokensChange: (value: number, index: number) => void;
  onDelete: (index: number) => void;
  modelNames: string[];
}> = ({
  model,
  maxToken,
  providerName,
  index,
  onModelChange,
  onMaxTokensChange,
  onDelete,
  modelNames,
}) => {
  return (
    <Box>
      <Box
        sx={{
          mt: index > 0 ? 2 : 0,
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          width: '100%',
        }}>
        <Box sx={{width: '75%'}}>
          <TextField
            placeholder="Enter model name..."
            value={model}
            onChange={value => {
              const newValue = value.replace(/\s/g, '');
              onModelChange(newValue, index);
            }}
            errorState={
              providerName.length + model.length > 127 ||
              modelNames.some((m, i) => i !== index && m === model)
            }
          />
        </Box>
        <Box sx={{width: '25%'}}>
          <TextField
            placeholder="Max tokens..."
            type="number"
            value={String(maxToken || '')}
            onChange={value => {
              const newValue = value.replace(/[^0-9]/g, '');
              const numericValue = newValue ? parseInt(newValue, 10) : 0;
              onMaxTokensChange(numericValue, index);
            }}
          />
        </Box>
        <Button variant="ghost" icon="delete" onClick={() => onDelete(index)} />
      </Box>
      {/* Error messages */}
      {providerName.length + model.length > 127 && (
        <Typography
          variant="caption"
          color="error"
          sx={{
            ...sharedTypographyStyle,
            mt: 0.5,
            display: 'block',
          }}>
          {'<Provider>/<Model> cannot be more than 128 characters'}
        </Typography>
      )}
      {modelNames.some((m, i) => i !== index && m === model) && (
        <Typography
          variant="caption"
          color="error"
          sx={{
            ...sharedTypographyStyle,
            mt: 0.5,
            display: 'block',
          }}>
          Model name must be unique
        </Typography>
      )}
    </Box>
  );
};

// Provider name component
export const ProviderNameInput: React.FC<{
  name: string;
  onNameChange: (value: string) => void;
  nameIsUnique: boolean;
  providers: string[];
}> = ({name, onNameChange, nameIsUnique, providers}) => {
  const nameNoSpaces = name.includes(' ') === false;

  return (
    <Box>
      <Typography sx={{...sharedTypographyStyle, mb: 1, fontWeight: '600'}}>
        Provider name
      </Typography>
      <TextField
        placeholder="Enter provider name..."
        value={name}
        onChange={value => onNameChange(value)}
        errorState={!nameIsUnique || !nameNoSpaces || name.length > 128}
      />
      {!nameIsUnique && (
        <Typography
          variant="caption"
          color="error"
          sx={{...sharedTypographyStyle, mt: 0.5}}>
          Provider with this name already exists
        </Typography>
      )}
      {!nameNoSpaces && (
        <Typography
          variant="caption"
          color="error"
          sx={{...sharedTypographyStyle, mt: 0.5}}>
          Name cannot contain spaces
        </Typography>
      )}
      {name.length > 128 && (
        <Typography
          variant="caption"
          color="error"
          sx={{...sharedTypographyStyle, mt: 0.5}}>
          Name must be less than 128 characters
        </Typography>
      )}
    </Box>
  );
};

// API Key Input component
export const ApiKeyInput: React.FC<{
  apiKey: string;
  onApiKeyChange: (value: string) => void;
  projectId: string;
}> = ({apiKey, onApiKeyChange, projectId}) => {
  return (
    <Box>
      <Typography
        sx={{
          ...sharedTypographyStyle,
          fontWeight: '600',
          display: 'flex',
          alignItems: 'center',
          gap: 0.5,
        }}>
        API key
        <Tooltip
          trigger={
            <Icon name="key-admin" width={16} height={16} color="text-muted" />
          }
          content="Sourced from team secrets"
        />
      </Typography>
      <Typography
        sx={{
          ...sharedTypographyStyle,
          color: 'text.secondary',
          fontSize: '0.875rem',
        }}>
        API keys can be added in your
        <Link
          href={`/${projectId.split('/')[0]}/settings`}
          target="_blank"
          rel="noopener noreferrer"
          sx={{
            color: TEAL_600,
            '&:hover': {
              color: TEAL_500,
            },
            ml: 0.5,
            textDecoration: 'none',
          }}>
          team's secrets →
        </Link>
      </Typography>
      <Typography
        sx={{
          ...sharedTypographyStyle,
          color: 'text.secondary',
          fontSize: '0.875rem',
          mb: 1,
        }}>
        Note: Secrets are only available to team admins.
      </Typography>
      <TextField
        placeholder="WANDB_SECRET_NAME..."
        value={apiKey}
        onChange={value => onApiKeyChange(value)}
      />
    </Box>
  );
};

// Base URL Input component
export const BaseUrlInput: React.FC<{
  baseUrl: string;
  onBaseUrlChange: (value: string) => void;
}> = ({baseUrl, onBaseUrlChange}) => {
  return (
    <Box>
      <Typography sx={{...sharedTypographyStyle, fontWeight: '600'}}>
        Base URL
      </Typography>
      <Typography
        sx={{
          ...sharedTypographyStyle,
          color: 'text.secondary',
          fontSize: '0.875rem',
          mb: 1,
        }}>
        For example: https://api.yourendpoint.com/v1
      </Typography>
      <TextField
        placeholder="Enter base URL..."
        value={baseUrl}
        onChange={value => onBaseUrlChange(value)}
      />
    </Box>
  );
};

// Whole models section component
export const ModelsSection: React.FC<{
  modelNames: string[];
  maxTokens: number[];
  providerName: string;
  onAddModel: () => void;
  onModelChange: (value: string, index: number) => void;
  onMaxTokensChange: (value: number, index: number) => void;
  onDeleteModel: (index: number) => void;
}> = ({
  modelNames,
  maxTokens,
  providerName,
  onAddModel,
  onModelChange,
  onMaxTokensChange,
  onDeleteModel,
}) => {
  return (
    <Box>
      <Box
        sx={{
          mb: 2,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}>
        <Typography
          sx={{
            ...sharedTypographyStyle,
            fontWeight: '600',
            display: 'flex',
            alignItems: 'center',
            gap: 0.5,
          }}>
          Models
          <Tooltip
            trigger={
              <Icon name="info" width={16} height={16} color="text-muted" />
            }
            content="Models are the specific AI models you want to use from the provider. You can add multiple models to the same provider."
          />
        </Typography>
        <Button
          variant="secondary"
          size="small"
          icon="add-new"
          onClick={onAddModel}>
          Add a model
        </Button>
      </Box>
      {modelNames.map((model, index) => (
        <ModelInput
          key={index}
          model={model}
          maxToken={maxTokens[index]}
          providerName={providerName}
          index={index}
          onModelChange={onModelChange}
          onMaxTokensChange={onMaxTokensChange}
          onDelete={onDeleteModel}
          modelNames={modelNames}
        />
      ))}
    </Box>
  );
};
