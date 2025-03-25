import {Box, Link} from '@mui/material';
import {toast} from '@wandb/weave/common/components/elements/Toast';
import {
  MOON_200,
  TEAL_500,
  TEAL_600,
} from '@wandb/weave/common/css/color.styles';
import {useHandleScroll} from '@wandb/weave/common/hooks/useHandleScroll';
import {Button} from '@wandb/weave/components/Button';
import React, {useEffect, useState} from 'react';

import {ResizableDrawer} from '../common/ResizableDrawer';
import {findMaxTokensByModelName} from '../PlaygroundPage/llmMaxTokens';
import {useCreateBuiltinObjectInstance} from '../wfReactInterface/objectClassQuery';
import {
  ApiKeyInput,
  BaseUrlInput,
  HeadersInput,
  ModelsSection,
  ProviderDrawerHeader,
  ProviderNameInput,
} from './AddProviderDrawerFormComponents';

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
  const {scrollWidth} = useHandleScroll();
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
          project_id: projectId,
          object_id: name,
          val: {
            name,
            base_url: baseUrl,
            api_key_name: apiKey,
            extra_headers:
              headers
                ?.filter(([key, value]) => key !== '')
                .reduce((acc, [key, value]) => {
                  acc[key] = value;
                  return acc;
                }, {} as Record<string, string>) || {},
          },
        },
      });

      toast(`Provider ${name} ${editingProvider ? 'updated' : 'created'}`, {
        type: 'success',
      });
    } catch (error) {
      console.error(error);
      toast(`Failed to create provider: ${error}`, {
        type: 'error',
      });
    }

    try {
      if (result?.digest) {
        await Promise.all(
          modelName.map(async (model, index) => {
            if (model === '') {
              return '';
            }
            return await createProviderModel({
              obj: {
                val: {
                  name: model,
                  provider: result.digest,
                  max_tokens:
                    maxTokens[index] || findMaxTokensByModelName(model),
                },
                project_id: projectId,
                // Object ID is the provider name + '/' + model name
                object_id: name + '/' + model,
              },
            });
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

  const hasDuplicateModelNames = modelName.some(
    (model, index) => modelName.findIndex(m => m === model) !== index
  );

  const disableSave =
    name.length === 0 ||
    apiKey.length === 0 ||
    baseUrl.length === 0 ||
    !nameIsUnique ||
    hasDuplicateModelNames;

  const handleToggleFullscreen = () => {
    setIsFullscreen(!isFullscreen);
  };

  return (
    <ResizableDrawer
      open={isOpen}
      onClose={handleClose}
      // if the navbar is visible, we need to offset the drawer by the height of the navbar
      marginTop={Math.min(60 - scrollWidth, 60)}
      defaultWidth={isFullscreen ? window.innerWidth - 73 : drawerWidth}
      setWidth={width => !isFullscreen && setDrawerWidth(width)}
      headerContent={
        <ProviderDrawerHeader
          title={editingProvider ? 'Edit AI provider' : 'Add AI provider'}
          isFullscreen={isFullscreen}
          onToggleFullscreen={handleToggleFullscreen}
          onClose={handleClose}
        />
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
            <CustomProviderInfoBanner />

            <ProviderNameInput
              name={name}
              onNameChange={setName}
              nameIsUnique={nameIsUnique}
              providers={providers}
            />

            <ApiKeyInput
              apiKey={apiKey}
              onApiKeyChange={setApiKey}
              projectId={projectId}
            />

            <BaseUrlInput baseUrl={baseUrl} onBaseUrlChange={setBaseUrl} />

            <HeadersInput headers={headers} onHeadersChange={setHeaders} />

            <ModelsSection
              modelNames={modelName}
              maxTokens={maxTokens}
              providerName={name}
              onAddModel={() => {
                setModelName([...modelName, '']);
                setMaxTokens([...maxTokens, 0]);
              }}
              onModelChange={(value, idx) => {
                setModelName(prev =>
                  prev.map((m, i) => (i === idx ? value : m))
                );
              }}
              onMaxTokensChange={(value, idx) => {
                setMaxTokens(prev =>
                  prev.map((m, i) => (i === idx ? value : m))
                );
              }}
              onDeleteModel={idx => {
                setModelName(prev => prev.filter((_, i) => i !== idx));
                setMaxTokens(prev => prev.filter((_, i) => i !== idx));
              }}
            />
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

const CustomProviderInfoBanner = () => (
  <Box
    style={{
      backgroundColor: MOON_200,
      padding: '16px',
      borderRadius: '8px',
      marginBottom: '-8px',
    }}>
    Custom providers are made for connecting to OpenAI compatible API endpoints.
    Please refer to the {/* TODO: Add link to custom provider documentation */}
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
);
