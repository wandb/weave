import {Box} from '@mui/material';
import {toast} from '@wandb/weave/common/components/elements/Toast';
import {MOON_200, MOON_500} from '@wandb/weave/common/css/color.styles';
import {useInsertSecret} from '@wandb/weave/common/hooks/useSecrets';
import {Button} from '@wandb/weave/components/Button';
import {Select} from '@wandb/weave/components/Form/Select';
import {TextField} from '@wandb/weave/components/Form/TextField';
import React, {useEffect, useState} from 'react';

import {ResizableDrawer} from '../../common/ResizableDrawer';
import {
  LLM_PROVIDER_LABELS,
  LLM_PROVIDER_SECRETS,
  LLM_PROVIDERS,
} from '../llmMaxTokens';

type Provider = keyof typeof LLM_PROVIDER_LABELS;

type ProviderOption = {
  label: string;
  value: Provider;
};

interface ProviderConfigDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  entity: string;
  defaultProvider?: Provider;
}

export const ProviderConfigDrawer: React.FC<ProviderConfigDrawerProps> = ({
  isOpen,
  onClose,
  entity,
  defaultProvider = 'openai',
}) => {
  const [selectedProvider, setSelectedProvider] =
    useState<(typeof LLM_PROVIDERS)[number]>(defaultProvider);
  const [apiKeys, setApiKeys] = useState<string[]>(
    LLM_PROVIDER_SECRETS[defaultProvider]?.map(secret => '') || ['']
  );
  const insertSecret = useInsertSecret();

  const providerOptions = LLM_PROVIDERS.map(provider => ({
    label: LLM_PROVIDER_LABELS[provider],
    value: provider,
  }));

  const handleSave = async () => {
    const secretNames = LLM_PROVIDER_SECRETS[selectedProvider];
    if (!secretNames) {
      console.error('No secret name found for provider:', selectedProvider);
      return;
    }
    secretNames.forEach(async (secretName, index) => {
      try {
        await insertSecret({
          variables: {
            entityName: entity,
            secretName,
            secretValue: apiKeys[index],
          },
        });
        toast('Provider secret saved successfully');
        onClose();
        setApiKeys([]);
      } catch (error) {
        console.error('Error saving secret:', error);
        toast('Error saving secret', {
          type: 'error',
        });
      }
    });
  };

  const getSecretKeyLabel = (provider: Provider) => {
    const secretName = LLM_PROVIDER_SECRETS[provider]?.[0];
    if (!secretName) {
      return 'This key will be saved securely as a team secret.';
    }
    if (LLM_PROVIDER_SECRETS[provider]?.length > 1) {
      return `These keys will be saved securely as team secrets named ${LLM_PROVIDER_SECRETS[
        provider
      ]
        ?.map(secret => `"${secret}"`)
        .join(', ')}, and will be available for your entire team.`;
    }
    return `This key will be saved securely as a team secret named ${secretName}, and will be available for your entire team.`;
  };

  useEffect(() => {
    if (defaultProvider) {
      setSelectedProvider(defaultProvider);
      setApiKeys(
        LLM_PROVIDER_SECRETS[defaultProvider]?.map(secret => '') || ['']
      );
    }
  }, [defaultProvider]);

  const drawerContent = (
    <>
      <Box
        sx={{
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}>
        <Box
          sx={{
            flex: 1,
            p: 3,
            overflowY: 'auto',
            overflowX: 'hidden',
          }}>
          <Box sx={{display: 'flex', flexDirection: 'column', gap: '24px'}}>
            <Box>
              <Box
                sx={{marginBottom: '8px', fontWeight: 600, fontSize: '16px'}}>
                Provider
              </Box>
              <Select<ProviderOption, false>
                value={providerOptions.find(
                  opt => opt.value === selectedProvider
                )}
                onChange={option => {
                  if (option) {
                    setSelectedProvider(option.value);
                    setApiKeys(
                      LLM_PROVIDER_SECRETS[option.value]?.map(secret => '') ||
                        []
                    );
                  }
                }}
                options={providerOptions}
              />
            </Box>

            <Box>
              <Box sx={{fontWeight: 600, fontSize: '16px'}}>
                {LLM_PROVIDER_LABELS[selectedProvider]} API key
                {apiKeys.length > 1 && 's'}
              </Box>
              <Box
                sx={{marginBottom: '8px', color: MOON_500, fontSize: '14px'}}>
                {getSecretKeyLabel(selectedProvider)}
              </Box>
              <Box sx={{display: 'flex', flexDirection: 'column', gap: '8px'}}>
                {apiKeys.map((apiKey, index) => (
                  <Box key={index}>
                    <Box sx={{fontWeight: 400, fontSize: '14px', mb: '4px'}}>
                      {LLM_PROVIDER_SECRETS[selectedProvider]?.[index]}
                    </Box>
                    <TextField
                      value={apiKey}
                      onChange={value => {
                        const newApiKeys = [...apiKeys];
                        newApiKeys[index] = value;
                        setApiKeys(newApiKeys);
                      }}
                      placeholder="Enter API key"
                      type="password"
                    />
                  </Box>
                ))}
              </Box>
            </Box>
          </Box>
        </Box>

        <Box
          sx={{
            py: 2,
            px: 0,
            borderTop: '1px solid',
            borderColor: MOON_200,
            backgroundColor: 'background.paper',
            width: '100%',
            display: 'flex',
            flexShrink: 0,
            position: 'sticky',
            bottom: 0,
          }}>
          <Box sx={{display: 'flex', gap: 2, width: '100%', mx: 3}}>
            <Button
              onClick={onClose}
              variant="secondary"
              style={{flex: 1}}
              twWrapperStyles={{flex: 1}}>
              Cancel
            </Button>
            <Button
              onClick={handleSave}
              disabled={!apiKeys.every(key => key.trim() !== '')}
              variant="primary"
              style={{flex: 1}}
              twWrapperStyles={{flex: 1}}>
              Save provider
            </Button>
          </Box>
        </Box>
      </Box>
    </>
  );

  return (
    <ResizableDrawer
      open={isOpen}
      onClose={onClose}
      defaultWidth={500}
      headerContent={
        <Box
          sx={{
            padding: '16px 20px',
            borderBottom: `1px solid ${MOON_200}`,
            fontSize: '20px',
            fontWeight: 600,
          }}>
          Configure an LLM provider
        </Box>
      }>
      {drawerContent}
    </ResizableDrawer>
  );
};
