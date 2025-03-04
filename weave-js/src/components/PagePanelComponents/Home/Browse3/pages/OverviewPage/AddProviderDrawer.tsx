import React, {useEffect, useState} from 'react';
import {Drawer, TextField, Typography, Box, Divider} from '@mui/material';
import {Button} from '@wandb/weave/components/Button';
import {useCreateBuiltinObjectInstance} from '../wfReactInterface/objectClassQuery';
import {Tooltip} from '@wandb/weave/components/Tooltip';
import {Icon} from '@wandb/weave/components/Icon';
import {findMaxTokensByModelName} from '../PlaygroundPage/llmMaxTokens';
import {toast} from '@wandb/weave/common/components/elements/Toast';

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

  useEffect(() => {
    if (editingProvider) {
      setName(editingProvider.name);
      setApiKey(editingProvider.apiKey);
      setBaseUrl(editingProvider.baseUrl);
      setModelName(editingProvider.models);
      setHeaders(editingProvider.headers);
    }
  }, [editingProvider]);

  // Reset form on close
  const handleClose = () => {
    setName('');
    setApiKey('');
    setBaseUrl('');
    setModelName([]);
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
        modelDigests = await Promise.all(
          modelName.map(async model => {
            const modelResult = await createProviderModel({
              obj: {
                val: {
                  name: model,
                  provider: result.digest,
                  max_tokens: findMaxTokensByModelName(model),
                },
                project_id: projectId,
                object_id: name + '-' + model,
              },
            });
            return modelResult.digest;
          })
        );
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

  const disableSave =
    name.length === 0 ||
    apiKey.length === 0 ||
    baseUrl.length === 0 ||
    !nameIsUnique ||
    !nameNoSpaces;

  return (
    <Drawer
      anchor="right"
      open={isOpen}
      onClose={handleClose}
      PaperProps={{
        sx: {
          width: 480,
          marginTop: '60px',
          height: 'calc(100% - 60px)',
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
                fullWidth
                size="small"
                placeholder="Enter unique name"
                variant="outlined"
                value={name}
                onChange={e => setName(e.target.value)}
                error={!nameIsUnique || !nameNoSpaces || name.length > 128}
                helperText={
                  !nameIsUnique
                    ? 'Provider with this name already exists'
                    : !nameNoSpaces
                    ? 'Name cannot contain spaces'
                    : name.length > 128
                    ? 'Name must be less than 128 characters'
                    : ''
                }
              />
            </Box>

            <Box>
              <Typography variant="subtitle2" sx={{mb: 1, fontWeight: 'bold'}}>
                API key name
              </Typography>
              <TextField
                fullWidth
                size="small"
                placeholder="Enter secret name"
                variant="outlined"
                value={apiKey}
                onChange={e => setApiKey(e.target.value.replace(/\s/g, ''))}
              />
            </Box>

            <Box>
              <Typography variant="subtitle2" sx={{mb: 1, fontWeight: 'bold'}}>
                API base URL
              </Typography>
              <TextField
                fullWidth
                size="small"
                placeholder="Enter API base URL"
                variant="outlined"
                value={baseUrl}
                onChange={e => setBaseUrl(e.target.value.replace(/\s/g, ''))}
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
                  <Box key={index} sx={{display: 'flex', alignItems: 'center'}}>
                    <TextField
                      fullWidth
                      size="small"
                      value={key}
                      sx={{mr: 1}}
                      onChange={e =>
                        setHeaders(prev =>
                          prev.map(([k, v], i) =>
                            i === index ? [e.target.value, v] : [k, v]
                          )
                        )
                      }
                    />
                    <TextField
                      fullWidth
                      size="small"
                      value={value}
                      onChange={e =>
                        setHeaders(prev =>
                          prev.map(([k, v], i) =>
                            i === index
                              ? ([k, e.target.value] as [string, string])
                              : [k, v]
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
                  mb: 1,
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
                  onClick={() => setModelName([...modelName, ''])}>
                  Add a model
                </Button>
              </Box>
              {modelName.map((model, index) => (
                <Box
                  key={index}
                  sx={{
                    mt: index > 0 ? 2 : 0,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                    width: '100%',
                  }}>
                  <Box sx={{flexGrow: 1}}>
                    <TextField
                      fullWidth
                      size="small"
                      placeholder="Enter model name"
                      variant="outlined"
                      value={model}
                      onChange={e => {
                        const newValue = e.target.value.replace(/\s/g, '');
                        setModelName(prev =>
                          prev.map((m, i) => (i === index ? newValue : m))
                        );
                      }}
                      error={name.length + model.length > 127}
                      helperText={
                        name.length + model.length > 127
                          ? `<Provider>/<Model> cannot be more than 128 characters`
                          : ''
                      }
                    />
                  </Box>
                  <Button
                    variant="ghost"
                    size="small"
                    icon="delete"
                    onClick={() =>
                      setModelName(prev => prev.filter((_, i) => i !== index))
                    }
                  />
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
