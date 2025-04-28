import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardActions from '@mui/material/CardActions';
import CardContent from '@mui/material/CardContent';
import Drawer from '@mui/material/Drawer';
import Grid from '@mui/material/Grid2';
import TextField from '@mui/material/TextField';
import {
  useInsertSecret,
  useSecrets,
} from '@wandb/weave/common/hooks/useSecrets';
import {TargetBlank} from '@wandb/weave/common/util/links';
import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {useHistory} from 'react-router';
import {Link} from 'react-router-dom';

import {SimplePageLayout} from './common/SimplePageLayout';

type Mod = {
  name: string;
  description: string;
  version: string;
  classifiers: string[];
  secrets: string[];
};

type ModCategories = {
  [key: string]: Mod[];
};

// Default empty categories to avoid undefined errors before data loads
const defaultModCats: ModCategories = {
  Guardrails: [],
  Analysis: [],
  Demos: [],
};

// To keep things simple we just fetch from github
// TODO: switch to https://modsctl.wandb.tools/mods.json once we wire the url through
const MOD_MANIFEST_URL =
  'https://raw.githubusercontent.com/wandb/weave-mods/refs/heads/main/featured-mods.json';

const ModCategory: React.FC<{
  category: string;
  mods: Mod[];
  entity: string;
  project: string;
}> = ({category, mods, entity, project}) => {
  return (
    <Box>
      <h5
        style={{
          fontWeight: 600,
          opacity: 0.8,
          fontSize: '1.1rem',
          padding: '0.5em 1em',
          marginBottom: 0,
        }}>
        {category}
      </h5>
      <ModCards mods={mods} entity={entity} project={project} />
    </Box>
  );
};

const ModCards: React.FC<{mods: Mod[]; entity: string; project: string}> = ({
  mods,
  entity,
  project,
}) => {
  const searchParams = new URLSearchParams(window.location.search);
  const [gistId, setGistId] = useState('');

  const purl =
    searchParams.get('purl') ||
    (gistId !== '' ? encodeURIComponent(`pkg:gist/${gistId}`) : '');
  return (
    <Grid container spacing={2} sx={{padding: '1em'}}>
      {mods.map(mod => (
        <Grid size={3} key={mod.name}>
          <Card variant="outlined" sx={{height: 180}}>
            <CardContent>
              <h5 style={{fontWeight: 600, fontSize: '1.15rem'}}>{mod.name}</h5>
              <p>{mod.description}</p>
            </CardContent>
            <CardActions>
              {mod.name === 'gist' && (
                <TextField
                  size="small"
                  id="gist"
                  label="Gist ID"
                  variant="outlined"
                  value={gistId}
                  onChange={e => setGistId(e.target.value)}
                />
              )}
              <Button
                component={Link}
                to={`/${entity}/${project}/weave/mods/${encodeURIComponent(
                  mod.name
                )}?purl=${purl}&checkSecrets=true`}
                size="small">
                Run
              </Button>
            </CardActions>
          </Card>
        </Grid>
      ))}
    </Grid>
  );
};

const ModFrame: React.FC<{entity: string; project: string; modId: string}> = ({
  entity,
  project,
  modId,
}) => {
  const searchParams = new URLSearchParams(window.location.search);
  const purl = searchParams.get('purl');
  const history = useHistory();
  const modUrl = `${
    window.WEAVE_CONFIG.WANDB_BASE_URL
  }/service-redirect/${entity}/${project}/${encodeURIComponent(
    modId
  )}/mod?purl=${purl}`;
  const iframeRef = useRef<HTMLIFrameElement>(null);

  const setupIframeAuth = useCallback(
    (iframe: HTMLIFrameElement) => {
      const authListener = (event: MessageEvent) => {
        if (!event.data.type || !event.data.type.startsWith('MOD_AUTH_')) {
          return;
        }

        switch (event.data.type) {
          case 'MOD_AUTH_RESET':
            history.push(`/${entity}/${project}/weave/mods`);
            break;
          case 'MOD_AUTH_READY':
            // Bridge page loaded, trigger auth
            console.log('initiating auth from ModsPage', event.origin);
            iframe.contentWindow?.postMessage(
              {type: 'MOD_AUTH_START'},
              event.origin
            );
            break;
          case 'MOD_AUTH_COMPLETE':
            // Check if modDomain and originHostname share the same base domain.
            // This is important to prevent a mod from redirecting the iframe
            // to a malicious site.
            const getBaseDomain = (domain?: string) => {
              const parts = (domain || '').split('.');
              return parts.length > 2 ? parts.slice(1).join('.') : domain;
            };

            const modBaseDomain = getBaseDomain(event.data.modDomain);
            const originBaseDomain = getBaseDomain(event.origin);
            console.log('auth completed, loading: ', event.data.modDomain);
            // enforce: modsctl.wandb.tools -> xxxxx.wandb.tools
            if (modBaseDomain === originBaseDomain) {
              iframe.src = `https://${event.data.modDomain}`;
            } else {
              console.error('invalid auth event');
            }
            break;
          case 'MOD_AUTH_ERROR':
            console.error(event.data.error);
            break;
        }
      };

      window.addEventListener('message', authListener);
      iframe.src = modUrl;
      return () => window.removeEventListener('message', authListener);
    },
    [modUrl, history, entity, project]
  );

  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe) {
      return;
    }
    return setupIframeAuth(iframe);
  }, [setupIframeAuth]);

  return (
    <iframe
      ref={iframeRef}
      style={{
        width: '100%',
        height: 'calc(100vh - 60px)',
        border: 0,
        borderImage:
          'linear-gradient(90deg, rgb(255, 75, 75), rgb(255, 253, 128)) 1',
        borderTop: '3px solid',
      }}
      title="Weave Mod"
      allow="window-placement 'self'; downloads 'self'; clipboard-write 'self'; accelerometer 'self'; ambient-light-sensor 'self'; autoplay 'self'; battery 'self'; camera 'self'; clipboard-read 'self'; display-capture 'self'; document-domain 'self'; encrypted-media 'self'; fullscreen 'self'; geolocation 'self'; gyroscope 'self'; layout-animations 'self'; legacy-image-formats 'self'; magnetometer 'self'; microphone 'self'; midi 'self'; oversized-images 'self'; payment 'self'; picture-in-picture 'self'; publickey-credentials-get 'self'; sync-xhr 'self'; usb 'self'; vr 'self'; wake-lock 'self'; xr-spatial-tracking 'self'"
      sandbox="allow-downloads allow-forms allow-modals allow-pointer-lock allow-popups allow-popups-to-escape-sandbox allow-same-origin allow-scripts allow-storage-access-by-user-activation"
    />
  );
};

export const SecretSettings: React.FC<{
  entity: string;
  project: string;
  modId: string | undefined;
  purl: string | null;
  secretNames: string[];
}> = ({entity, project, modId, purl, secretNames}) => {
  const helpText: Record<string, string> = {
    OPENAI_API_KEY: 'https://platform.openai.com/api-keys',
    ANTHROPIC_API_KEY: 'https://console.anthropic.com/keys',
    TOGETHER_API_KEY: 'https://api.together.ai/settings/api-keys',
  };
  const history = useHistory();
  const [open, setOpen] = useState(true);
  const carryOn = useCallback(() => {
    history.push(
      `/${entity}/${project}/weave/mods/${encodeURIComponent(
        modId || ''
      )}?purl=${purl || ''}`
    );
  }, [history, entity, project, modId, purl]);
  const closeDrawer = useCallback(() => {
    setOpen(false);
    // TODO: maybe don't allow this?
    carryOn();
  }, [setOpen, carryOn]);
  const [error, setError] = useState<string | null>(null);
  const {secrets: existingSecrets, loading} = useSecrets({
    entityName: entity,
  });
  const insertSecret = useInsertSecret();
  const [secrets, setSecrets] = useState<Record<string, string>>({});
  const missingSecrets: string[] = useMemo(() => {
    return secretNames.filter(
      name => !existingSecrets.includes(name) && name !== 'WANDB_API_KEY'
    );
  }, [secretNames, existingSecrets]);
  useEffect(() => {
    if (!loading && missingSecrets.length === 0) {
      carryOn();
    }
  }, [loading, missingSecrets.length, carryOn]);

  const handleChange = (
    event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
    name: string
  ) => {
    setSecrets(prevSecrets => ({...prevSecrets, [name]: event.target.value}));
  };
  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const emptySecrets = missingSecrets.filter(name => !secrets[name]?.trim());
    if (emptySecrets.length > 0) {
      setError(`Please provide values for: ${emptySecrets.join(', ')}`);
      return;
    }

    setError(null);
    await Promise.all(
      Object.entries(secrets).map(([name, value]) =>
        insertSecret({
          variables: {entityName: entity, secretName: name, secretValue: value},
        })
      )
    );
    carryOn();
  };
  if (loading) {
    return <></>;
  }
  if (missingSecrets.length === 0) {
    return <></>;
  }
  return (
    <Drawer anchor="right" open={open} onClose={closeDrawer}>
      <Box sx={{width: 400, padding: '4em 1em'}}>
        <h3>Required Secrets</h3>
        <p>
          The mod you've chosen requires the following secrets which currently
          don't exist. You can set them here or in your team settings page.
        </p>
        <form onSubmit={handleSubmit} autoComplete="off">
          {missingSecrets.map((name, idx) => (
            <Box key={name} mb={2}>
              <TextField
                label={name}
                type="password"
                variant="standard"
                fullWidth
                autoComplete="new-password"
                id={`secret-${idx}`}
                name={`secret-${idx}`}
                helperText={
                  helpText[name] ? (
                    <TargetBlank
                      href={helpText[name]}
                      target="_blank"
                      rel="noreferrer">
                      {helpText[name]}
                    </TargetBlank>
                  ) : undefined
                }
                value={secrets[name] || ''}
                onChange={event => handleChange(event, name)}
              />
            </Box>
          ))}
          {error && <Box sx={{color: 'error.main', mb: 2}}>{error}</Box>}
          <Button variant="contained" color="primary" type="submit">
            Run Mod
          </Button>
        </form>
      </Box>
    </Drawer>
  );
};

export const ModsPage: React.FC<{
  entity: string;
  project: string;
  itemName?: string;
}> = ({entity, project, itemName}) => {
  const searchParams = new URLSearchParams(window.location.search);
  const checkSecrets = searchParams.get('checkSecrets');
  const purl = searchParams.get('purl');
  const [modCats, setModCats] = useState<ModCategories>(defaultModCats);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchModCats = async () => {
      try {
        // MOD_MANIFEST_URL will always be absolute either to github or modsctl.wandb.tools
        // eslint-disable-next-line wandb/no-unprefixed-urls
        const response = await fetch(MOD_MANIFEST_URL);
        if (!response.ok) {
          throw new Error(`Failed to fetch mods: ${response.status}`);
        }
        const data = await response.json();
        setModCats(data);
      } catch (error) {
        console.error('Error fetching mod categories:', error);
        // Keep default categories on error
      } finally {
        setLoading(false);
      }
    };

    fetchModCats();
  }, []);

  const mod = itemName
    ? Object.values(modCats)
        .flat()
        .find((m: Mod) => m.name === itemName)
    : undefined;
  const secrets = mod?.secrets ?? [];

  return itemName && !checkSecrets ? (
    <ModFrame entity={entity} project={project} modId={itemName} />
  ) : (
    <SimplePageLayout
      title={'Mods'}
      hideTabsIfSingle
      tabs={[
        {
          label: '',
          content: (
            <Box
              sx={{
                flex: '1 1 auto',
                width: '100%',
                height: '100%',
                display: 'flex',
                overflow: 'scroll',
                paddingTop: '1em',
                flexDirection: 'column',
              }}>
              {loading ? (
                <Box
                  sx={{
                    display: 'flex',
                    justifyContent: 'center',
                    padding: '2em',
                  }}>
                  Loading mods...
                </Box>
              ) : (
                <>
                  {Object.entries(modCats)
                    .filter(([_, mods]) => mods && mods.length > 0)
                    .sort(
                      ([_A, modsA], [_B, modsB]) => modsA.length - modsB.length
                    )
                    .map(([category, mods]) => (
                      <ModCategory
                        key={category}
                        entity={entity}
                        project={project}
                        category={category}
                        mods={mods}
                      />
                    ))}
                </>
              )}
              {checkSecrets && (
                <SecretSettings
                  entity={entity}
                  project={project}
                  modId={itemName}
                  purl={purl}
                  secretNames={secrets}
                />
              )}
            </Box>
          ),
        },
      ]}
    />
  );
};
