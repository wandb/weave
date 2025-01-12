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
import React, {useCallback, useEffect, useMemo, useState} from 'react';
import {useHistory} from 'react-router';
import {Link} from 'react-router-dom';

import {SimplePageLayout} from './common/SimplePageLayout';

type Mod = {
  id: string;
  name: string;
  description: string;
  secrets: string[];
};

type ModCategoryType = 'Labeling' | 'Analysis' | 'Demos';

type ModCategories = {
  [key in ModCategoryType]: Mod[];
};

const modCats: ModCategories = {
  Labeling: [
    {
      id: 'labeling/html',
      name: 'HTML Labeler',
      description: 'Label generated HTML against your own criteria',
      secrets: ['WANDB_API_KEY', 'OPENAI_API_KEY'],
    },
  ],
  Analysis: [
    {
      id: 'embedding-classifier',
      name: 'Embedding Classifier',
      description:
        'Classify your traces by embedding them and have an LLM label the clusters',
      secrets: ['WANDB_API_KEY', 'OPENAI_API_KEY'],
    },
    {
      id: 'cost-dashboard',
      name: 'Cost Dashboard',
      description: 'A dashboard showing your project LLM costs over time',
      secrets: ['WANDB_API_KEY'],
    },
  ],
  Demos: [
    {
      id: 'welcome',
      name: 'Welcome',
      description: 'A simple welcome mod',
      secrets: ['WANDB_API_KEY'],
    },
    {
      id: 'openui',
      name: 'OpenUI',
      description: 'Generate UIs from images or text descriptions',
      secrets: ['WANDB_API_KEY', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY'],
    },
    {
      id: 'gist',
      name: 'Gist',
      description: 'Load a gist that contains a streamlit app.py file',
      secrets: ['WANDB_API_KEY'],
    },
  ],
};

const ModCategory: React.FC<{
  category: ModCategoryType;
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
        <Grid size={3} key={mod.id}>
          <Card variant="outlined" sx={{height: 180}}>
            <CardContent>
              <h5 style={{fontWeight: 600, fontSize: '1.15rem'}}>{mod.name}</h5>
              <p>{mod.description}</p>
            </CardContent>
            <CardActions>
              {mod.id === 'gist' && (
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
                  mod.id
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
  return (
    <iframe
      style={{
        width: '100%',
        height: '100vh',
        border: 0,
        borderImage:
          'linear-gradient(90deg, rgb(255, 75, 75), rgb(255, 253, 128)) 1',
        borderTop: '3px solid',
      }}
      title="Weave Mod"
      allow="accelerometer; ambient-light-sensor; autoplay; battery; camera; clipboard-read; clipboard-write; display-capture; document-domain; encrypted-media; fullscreen; geolocation; gyroscope; layout-animations; legacy-image-formats; magnetometer; microphone; midi; oversized-images; payment; picture-in-picture; publickey-credentials-get; sync-xhr; usb; vr; wake-lock; xr-spatial-tracking"
      sandbox="allow-downloads allow-forms allow-modals allow-pointer-lock allow-popups allow-popups-to-escape-sandbox allow-same-origin allow-scripts allow-storage-access-by-user-activation"
      src={`${
        window.WEAVE_CONFIG.WANDB_BASE_URL
      }/service-redirect/${entity}/${project}/${encodeURIComponent(
        modId
      )}/mod?purl=${purl}`}
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
  const mod = itemName
    ? Object.values(modCats)
        .flat()
        .find(m => m.id === itemName)
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
              <ModCategory
                entity={entity}
                project={project}
                category="Labeling"
                mods={modCats.Labeling}
              />
              <ModCategory
                entity={entity}
                project={project}
                category="Analysis"
                mods={modCats.Analysis}
              />
              <ModCategory
                entity={entity}
                project={project}
                category="Demos"
                mods={modCats.Demos}
              />
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
