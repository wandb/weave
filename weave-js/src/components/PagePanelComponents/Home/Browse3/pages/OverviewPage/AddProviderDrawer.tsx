import {Box, Link,Typography} from '@mui/material';
import {toast} from '@wandb/weave/common/components/elements/Toast';
import {MOON_200,TEAL_500, TEAL_600} from '@wandb/weave/common/css/color.styles';
import {Button} from '@wandb/weave/components/Button';
import {TextField} from '@wandb/weave/components/Form/TextField';
import {Icon} from '@wandb/weave/components/Icon';
import {Tooltip} from '@wandb/weave/components/Tooltip';
import React, {useEffect, useState} from 'react';

import {ResizableDrawer} from '../common/ResizableDrawer';
import {findMaxTokensByModelName} from '../PlaygroundPage/llmMaxTokens';
import {useCreateBuiltinObjectInstance} from '../wfReactInterface/objectClassQuery';

// Shared typography style
const sharedTypographyStyle = {
  fontSize: '16px',
  fontFamily: 'Source Sans Pro',
};

interface AddProviderDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: string;
  refetch: () => void;
  providers: string[];
  editingProvider?: {
    name: string;
    baseUrl: string;
    apiKey: string;
    models: string[];
    headers: Array<[string, string]>;
    maxTokens: number[];
  };
}

export const AddProviderDrawer: React.FC<AddProviderDrawerProps> = ({
  projectId,
  isOpen,
  onClose,
  refetch,
  providers,
  editingProvider,
}) => {
  const createProvider = useCreateBuiltinObjectInstance('Provider');
  const createProviderModel = useCreateBuiltinObjectInstance('ProviderModel');
  const [drawerWidth, setDrawerWidth] = useState(480);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Form state
  const [name, setName] = useState(editingProvider?.name || '');
  const [apiKey, setApiKey] = useState(editingProvider?.apiKey || '');
  const [baseUrl, setBaseUrl] = useState(editingProvider?.baseUrl || '');
  const [headers, setHeaders] = useState<Array<[string, string]>>(
    editingProvider?.headers || [['', '']]
  );
  const [modelName, setModelName] = useState<string[]>(
    editingProvider?.models || ['']
  );
  const [maxTokens, setMaxTokens] = useState<number[]>(
    editingProvider?.maxTokens || [0]
  );

  useEffect(() => {
    if (editingProvider) {
      setName(editingProvider.name);
      setApiKey(editingProvider.apiKey);
      setBaseUrl(editingProvider.baseUrl);
      setModelName(editingProvider.models);
      setHeaders(editingProvider.headers);
      setMaxTokens(editingProvider.maxTokens || []);
    }
  }, [editingProvider]);

  // Reset form on close
  const handleClose = () => {
    setName('');
    setApiKey('');
    setBaseUrl('');
    setModelName(['']);
    setMaxTokens([0]);
    setHeaders([['', '']]);
    onClose();
  };

  const handleSave = async () => {
    handleClose();

    let result: any;
    try {
      result = await createProvider({
        obj: {
          val: {
            name,
            base_url: baseUrl.replace(/\/+$/, ''),
            api_key_name: apiKey,
            extra_headers:
              headers
                ?.filter(([key, value]) => key !== '')
                .reduce((acc, [key, value]) => {
                  acc[key] = value;
                  return acc;
                }, {} as Record<string, string>) || {},
          },
          project_id: projectId,
          object_id: name,
        },
      });
    } catch (error) {
      console.error(error);
      toast(`Failed to create provider: ${error}`, {
        type: 'error',
      });
    }

    try {
      let modelDigests: string[] = [];
      if (result?.digest) {
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        modelDigests = (
          await Promise.all(
            modelName.map(async (model, index) => {
              if (model === '') {
                return '';
              }
              const modelResult = await createProviderModel({
                obj: {
                  val: {
                    name: model,
                    provider: result.digest,
                    max_tokens:
                      maxTokens[index] || findMaxTokensByModelName(model),
                  },
                  project_id: projectId,
                  object_id: name + '-' + model,
                },
              });
              return modelResult.digest;
            })
          )
        ).filter((digest: string) => digest !== '');
      }

      refetch();
    } catch (error) {
      console.error(error);
      toast(`Failed to create provider models: ${error}`, {
        type: 'error',
      });
    }
  };

  const nameIsUnique =
    !providers.includes(name) || name === editingProvider?.name;
  const nameNoSpaces = name.includes(' ') === false;

  const hasDuplicateModelNames = modelName.some(
    (model, index) => modelName.findIndex(m => m === model) !== index
  );

  const disableSave =
    name.length === 0 ||
    apiKey.length === 0 ||
    baseUrl.length === 0 ||
    !nameIsUnique ||
    !nameNoSpaces ||
    hasDuplicateModelNames;

  const handleToggleFullscreen = () => {
    setIsFullscreen(!isFullscreen);
  };

  return (
    <ResizableDrawer
      open={isOpen}
      onClose={handleClose}
      defaultWidth={isFullscreen ? window.innerWidth - 73 : drawerWidth}
      setWidth={width => !isFullscreen && setDrawerWidth(width)}
      headerContent={
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
            {editingProvider ? 'Edit AI provider' : 'Add AI provider'}
          </Typography>
          <Box sx={{display: 'flex', gap: 1}}>
            <Button
              onClick={handleToggleFullscreen}
              variant="ghost"
              icon={isFullscreen ? 'minimize-mode' : 'full-screen-mode-expand'}
              tooltip={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
            />
            <Button
              onClick={handleClose}
              variant="ghost"
              icon="close"
              tooltip="Close"
            />
          </Box>
        </Box>
      }>
      <Box
        sx={{
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}>
        {/* Content */}
        <Box
          sx={{
            flex: 1,
            p: 2,
            overflowY: 'auto',
            overflowX: 'hidden',
          }}>
          <Box sx={{display: 'flex', flexDirection: 'column', gap: '24px'}}>
            <Box
              style={{
                backgroundColor: MOON_200,
                padding: '16px',
                borderRadius: '8px',
                marginBottom: '-8px',
              }}>
              Custom providers are made for connecting to OpenAI compatible API endpoints. Please refer to the{' '}
              <Link
                href="#"
                target="_blank"
                rel="noopener noreferrer"
                sx={{
                  color: TEAL_600,
                  '&:hover': {
                    color: TEAL_500,
                  },
                  textDecoration: 'none',
                }}>
                custom AI provider documentation
              </Link>{' '}
              for more information.
            </Box>
            <Box>
              <Typography
                sx={{...sharedTypographyStyle, mb: 1, fontWeight: '600'}}>
                Provider name
              </Typography>
              <TextField
                placeholder="Enter provider name..."
                value={name}
                onChange={value => setName(value)}
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

            <Box>
              <Typography sx={{...sharedTypographyStyle, fontWeight: '600', display: 'flex', alignItems: 'center', gap: 0.5}}>
                API key
                <Tooltip
                  trigger={
                    <Icon
                      name="key-admin"
                      width={16}
                      height={16}
                      color="text-muted"
                    />
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
                onChange={value => setApiKey(value)}
              />
            </Box>

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
                onChange={value => setBaseUrl(value)}
              />
            </Box>

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
                    headers
                      ? setHeaders([...headers, ['', '']])
                      : setHeaders([['', '']])
                  }>
                  Add a header
                </Button>
              </Box>
              <Box sx={{display: 'flex', flexDirection: 'column', gap: 1}}>
                {headers?.map(([key, value], index) => (
                  <Box
                    key={index}
                    sx={{display: 'flex', alignItems: 'center', gap: 1}}>
                    <TextField
                      placeholder="Enter header key..."
                      value={key}
                      onChange={val =>
                        setHeaders(prev =>
                          prev.map(([k, v], i) =>
                            i === index ? [val, v] : [k, v]
                          )
                        )
                      }
                    />
                    <TextField
                      placeholder="Enter header value..."
                      value={value}
                      onChange={val =>
                        setHeaders(prev =>
                          prev.map(([k, v], i) =>
                            i === index ? [k, val] : [k, v]
                          )
                        )
                      }
                    />
                    <Button
                      variant="ghost"
                      icon="delete"
                      onClick={() =>
                        setHeaders(prev => {
                          const newHeaders = [...prev];
                          newHeaders.splice(index, 1);
                          return newHeaders;
                        })
                      }
                    />
                  </Box>
                ))}
              </Box>
            </Box>

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
                      <Icon
                        name="info"
                        width={16}
                        height={16}
                        color="text-muted"
                      />
                    }
                    content="Models are the specific AI models you want to use from the provider. You can add multiple models to the same provider."
                  />
                </Typography>
                <Button
                  variant="secondary"
                  size="small"
                  icon="add-new"
                  onClick={() => {
                    setModelName([...modelName, '']);
                    setMaxTokens([...maxTokens, 0]);
                  }}>
                  Add a model
                </Button>
              </Box>
              {modelName.map((model, index) => (
                <Box key={index}>
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
                          setModelName(prev =>
                            prev.map((m, i) => (i === index ? newValue : m))
                          );
                        }}
                        errorState={
                          name.length + modelName[index].length > 127 ||
                          modelName.some(
                            (m, i) => i !== index && m === modelName[index]
                          )
                        }
                      />
                    </Box>
                    <Box sx={{width: '25%'}}>
                      <TextField
                        placeholder="Max tokens..."
                        type="number"
                        value={String(maxTokens[index] || '')}
                        onChange={value => {
                          const newValue = value.replace(/[^0-9]/g, '');
                          const numericValue = newValue
                            ? parseInt(newValue, 10)
                            : 0;
                          setMaxTokens(prev => {
                            const newTokens = [...prev];
                            newTokens[index] = numericValue;
                            return newTokens;
                          });
                        }}
                      />
                    </Box>
                    <Button
                      variant="ghost"
                      icon="delete"
                      onClick={() => {
                        setModelName(prev =>
                          prev.filter((_, i) => i !== index)
                        );
                        setMaxTokens(prev =>
                          prev.filter((_, i) => i !== index)
                        );
                      }}
                    />
                  </Box>
                  {/* Error messages */}
                  {name.length + modelName[index].length > 127 && (
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
                  {modelName.some(
                    (m, i) => i !== index && m === modelName[index]
                  ) && (
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
              ))}
            </Box>
          </Box>
        </Box>

        {/* Footer */}
        <Box
          sx={{
            py: 2,
            px: 0,
            borderTop: '1px solid',
            borderColor: 'divider',
            backgroundColor: 'background.paper',
            width: '100%',
            display: 'flex',
            flexShrink: 0,
            position: 'sticky',
            bottom: 0,
          }}>
          <Box sx={{display: 'flex', gap: 2, width: '100%', mx: 2}}>
            <Button
              onClick={handleClose}
              variant="secondary"
              style={{flex: 1}}
              twWrapperStyles={{flex: 1}}>
              Cancel
            </Button>
            <Button
              onClick={handleSave}
              disabled={disableSave}
              variant="primary"
              style={{flex: 1}}
              twWrapperStyles={{flex: 1}}>
              {editingProvider ? 'Save' : 'Add provider'}
            </Button>
          </Box>
        </Box>
      </Box>
    </ResizableDrawer>
  );
};
