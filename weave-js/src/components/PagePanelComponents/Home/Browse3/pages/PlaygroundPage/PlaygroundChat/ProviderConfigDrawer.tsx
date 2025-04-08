import {Box} from '@mui/material';
import {toast} from '@wandb/weave/common/components/elements/Toast';
import {MOON_200, MOON_500} from '@wandb/weave/common/css/color.styles';
import {useInsertSecret} from '@wandb/weave/common/hooks/useSecrets';
import {Button} from '@wandb/weave/components/Button';
import {Select} from '@wandb/weave/components/Form/Select';
import {TextField} from '@wandb/weave/components/Form/TextField';
import React, {useState} from 'react';

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
  open: boolean;
  onClose: () => void;
  entity: string;
  defaultProvider?: Provider;
}

export const ProviderConfigDrawer: React.FC<ProviderConfigDrawerProps> = ({
  open,
  onClose,
  entity,
  defaultProvider = 'openai',
}) => {
  const [selectedProvider, setSelectedProvider] =
    useState<(typeof LLM_PROVIDERS)[number]>(defaultProvider);
  const [apiKey, setApiKey] = useState('');
  const insertSecret = useInsertSecret();

  const providerOptions = LLM_PROVIDERS.map(provider => ({
    label: LLM_PROVIDER_LABELS[provider],
    value: provider,
  }));

  const handleSave = async () => {
    const secretName = LLM_PROVIDER_SECRETS[selectedProvider]?.[0];
    if (!secretName) {
      console.error('No secret name found for provider:', selectedProvider);
      return;
    }
    try {
      await insertSecret({
        variables: {
          entityName: entity,
          secretName,
          secretValue: apiKey,
        },
      });
      toast('Provider secret saved successfully');
      onClose();
      setApiKey('');
    } catch (error) {
      console.error('Error saving secret:', error);
      toast('Error saving secret', {
        type: 'error',
      });
    }
  };

  const getSecretKeyLabel = (provider: Provider) => {
    const secretName = LLM_PROVIDER_SECRETS[provider]?.[0];
    if (!secretName) {
      return 'This key will be saved securely as a team secret.';
    }
    return `This key will be saved securely as a team secret named ${secretName}, and will be available for your entire team.`;
  };

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
                onChange={option => option && setSelectedProvider(option.value)}
                options={providerOptions}
              />
            </Box>

            <Box>
              <Box sx={{fontWeight: 600, fontSize: '16px'}}>
                {LLM_PROVIDER_LABELS[selectedProvider]} API key
              </Box>
              <Box
                sx={{marginBottom: '8px', color: MOON_500, fontSize: '14px'}}>
                {getSecretKeyLabel(selectedProvider)}
              </Box>
              <TextField
                value={apiKey}
                onChange={setApiKey}
                placeholder="Enter API key"
                type="password"
              />
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
              disabled={!apiKey}
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
      open={open}
      onClose={onClose}
      defaultWidth={500}
      headerContent={
        <Box
          sx={{
            padding: '24px',
            borderBottom: `1px solid ${MOON_200}`,
            fontSize: '32px',
            fontWeight: 600,
          }}>
          Configure an LLM provider
        </Box>
      }>
      {drawerContent}
    </ResizableDrawer>
  );
};
