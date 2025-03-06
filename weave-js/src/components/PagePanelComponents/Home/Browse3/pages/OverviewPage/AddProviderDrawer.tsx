import {Box, Divider, Drawer, Typography} from '@mui/material';
import {toast} from '@wandb/weave/common/components/elements/Toast';
import {useHandleScroll} from '@wandb/weave/common/hooks/useHandleScroll';
import {Button} from '@wandb/weave/components/Button';
import {TextField} from '@wandb/weave/components/Form/TextField';
import {Icon} from '@wandb/weave/components/Icon';
import {Tooltip} from '@wandb/weave/components/Tooltip';
import React, {useEffect, useState} from 'react';

import {findMaxTokensByModelName} from '../PlaygroundPage/llmMaxTokens';
import {useCreateBuiltinObjectInstance} from '../wfReactInterface/objectClassQuery';
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

  // Form state
  const [name, setName] = useState(editingProvider?.name || '');
  const [apiKey, setApiKey] = useState(editingProvider?.apiKey || '');
  const [baseUrl, setBaseUrl] = useState(editingProvider?.baseUrl || '');
  const [headers, setHeaders] = useState<Array<[string, string]>>(
    editingProvider?.headers || []
  );
  const [modelName, setModelName] = useState<string[]>(
    editingProvider?.models || []
  );
  const [maxTokens, setMaxTokens] = useState<number[]>(
    editingProvider?.maxTokens || []
  );

  const {scrolled} = useHandleScroll();

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
    setModelName([]);
    setMaxTokens([]);
    setHeaders([]);
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
            base_url: baseUrl,
            api_key_name: apiKey,
            extra_headers:
              headers?.reduce((acc, [key, value]) => {
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

  return (
    <Drawer
      anchor="right"
      open={isOpen}
      onClose={handleClose}
      PaperProps={{
        sx: {
          width: 480,
          marginTop: scrolled ? '0px' : '60px',
          height: scrolled ? '100%' : 'calc(100% - 60px)',
        },
      }}>
      <Box sx={{height: '100%', display: 'flex', flexDirection: 'column'}}>
        {/* Header */}
        <Box
          sx={{
            px: '16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            height: '64px',
          }}>
          <Typography variant="h6" fontWeight="semi-bold">
            {editingProvider ? 'Edit provider' : 'Add a provider'}
          </Typography>
          <Button variant="ghost" icon="close" onClick={handleClose} />
        </Box>
        <Divider />

        {/* Content */}
        <Box sx={{flex: 1, p: 3, overflowY: 'auto'}}>
          <Box sx={{display: 'flex', flexDirection: 'column', gap: 3}}>
            <Box>
              <Typography variant="subtitle2" sx={{mb: 1, fontWeight: 'bold'}}>
                Name
              </Typography>
              <TextField
                placeholder="Enter provider name"
                value={name}
                onChange={value => setName(value)}
                errorState={!nameIsUnique || !nameNoSpaces || name.length > 128}
              />
              {!nameIsUnique && (
                <Typography variant="caption" color="error" sx={{mt: 0.5}}>
                  Provider with this name already exists
                </Typography>
              )}
              {!nameNoSpaces && (
                <Typography variant="caption" color="error" sx={{mt: 0.5}}>
                  Name cannot contain spaces
                </Typography>
              )}
              {name.length > 128 && (
                <Typography variant="caption" color="error" sx={{mt: 0.5}}>
                  Name must be less than 128 characters
                </Typography>
              )}
            </Box>

            <Box>
              <Typography variant="subtitle2" sx={{mb: 1, fontWeight: 'bold'}}>
                API key name
              </Typography>
              <TextField
                placeholder="Enter API key name"
                value={apiKey}
                onChange={value => setApiKey(value)}
              />
            </Box>

            <Box>
              <Typography variant="subtitle2" sx={{mb: 1, fontWeight: 'bold'}}>
                API base URL
              </Typography>
              <TextField
                placeholder="Enter base URL"
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
                <Typography variant="subtitle2" sx={{fontWeight: 'bold'}}>
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
                      placeholder="Enter header key"
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
                      placeholder="Enter header value"
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
                      size="small"
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
                  variant="subtitle2"
                  sx={{
                    fontWeight: 'bold',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                  }}>
                  Models
                  <Tooltip
                    trigger={
                      <Icon name="info" size="small" color="text-muted" />
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
                        placeholder="Enter model name"
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
                        placeholder="Max tokens"
                        type="number"
                        value={String(maxTokens[index] || '')}
                        onChange={value => {
                          // Only allow numeric input
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
                      size="small"
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
                      sx={{mt: 0.5, display: 'block'}}>
                      {'<Provider>/<Model> cannot be more than 128 characters'}
                    </Typography>
                  )}
                  {modelName.some(
                    (m, i) => i !== index && m === modelName[index]
                  ) && (
                    <Typography
                      variant="caption"
                      color="error"
                      sx={{mt: 0.5, display: 'block'}}>
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
            p: 3,
            borderTop: '1px solid',
            borderColor: 'divider',
            display: 'flex',
            justifyContent: 'flex-end',
            gap: 1,
          }}>
          <Button variant="secondary" onClick={handleClose}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={disableSave}>
            Save
          </Button>
        </Box>
      </Box>
    </Drawer>
  );
};
