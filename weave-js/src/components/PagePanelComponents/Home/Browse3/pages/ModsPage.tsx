import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardActions from '@mui/material/CardActions';
import CardContent from '@mui/material/CardContent';
import Divider from '@mui/material/Divider';
import Grid from '@mui/material/Grid2';
import Typography from '@mui/material/Typography';
import React from 'react';
import {Link} from 'react-router-dom';

import {SimplePageLayout} from './common/SimplePageLayout';

type Mod = {
  id: string;
  name: string;
  description: string;
};

type ModCategoryType = 'Labeling' | 'Analysis' | 'Demos';

type ModCategories = {
  [key in ModCategoryType]: Mod[];
};

const mods: ModCategories = {
  Labeling: [
    {
      id: 'labeling/eval-forge',
      name: 'Eval Forge',
      description:
        'Create LLM judges using your existing traces and intelligence',
    },
    {
      id: 'labeling/html',
      name: 'HTML Labeler',
      description: 'Label generated HTML against your own criteria',
    },
  ],
  Analysis: [
    {
      id: 'coding-agents',
      name: 'Coding Agents',
      description: 'Analyize the effectiveness of code generation agents',
    },
    {
      id: 'embedding-classifier',
      name: 'Embedding Classifier',
      description:
        'Classify your traces by embedding them and have an LLM label the clusters',
    },
  ],
  Demos: [
    {
      id: 'openui',
      name: 'OpenUI',
      description: 'Generate UIs from images or text descriptions',
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
          fontSize: '1.2rem',
          padding: '0.5em 1em',
          marginBottom: 0,
        }}>
        {category}
      </h5>
      <Divider />
      <ModCards mods={mods} entity={entity} project={project} />
    </Box>
  );
};

const ModCards: React.FC<{mods: Mod[]; entity: string; project: string}> = ({
  mods,
  entity,
  project,
}) => {
  return (
    <Grid container spacing={2} sx={{padding: '1em'}}>
      {mods.map(mod => (
        <Grid size={3} key={mod.id}>
          <Card variant="outlined">
            <CardContent>
              <h5 style={{fontWeight: 600, fontSize: '1.15rem'}}>{mod.name}</h5>
              <p>{mod.description}</p>
            </CardContent>
            <CardActions>
              <Button
                component={Link}
                to={`/${entity}/${project}/weave/mods/${encodeURIComponent(
                  mod.id
                )}`}
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
  return (
    <iframe
      style={{width: '100%', height: '100vh', border: 'none'}}
      title="Weave Mod"
      allow="accelerometer; ambient-light-sensor; autoplay; battery; camera; clipboard-read; clipboard-write; display-capture; document-domain; encrypted-media; fullscreen; geolocation; gyroscope; layout-animations; legacy-image-formats; magnetometer; microphone; midi; oversized-images; payment; picture-in-picture; publickey-credentials-get; sync-xhr; usb; vr ; wake-lock; xr-spatial-tracking"
      sandbox="allow-downloads allow-forms allow-modals allow-pointer-lock allow-popups allow-popups-to-escape-sandbox allow-same-origin allow-scripts allow-storage-access-by-user-activation"
      src={`/service-redirect/${entity}/${project}/${modId}/mod`}
    />
  );
};

export const ModsPage: React.FC<{
  entity: string;
  project: string;
  itemName?: string;
}> = ({entity, project, itemName}) => {
  return itemName ? (
    <ModFrame entity={entity} project={project} modId={itemName} />
  ) : (
    <SimplePageLayout
      title={'Weave Mods'}
      hideTabsIfSingle
      tabs={[
        {
          label: '',
          content: (
            <>
              <ModCategory
                entity={entity}
                project={project}
                category="Labeling"
                mods={mods.Labeling}
              />
              <Divider />
              <ModCategory
                entity={entity}
                project={project}
                category="Analysis"
                mods={mods.Analysis}
              />
              <Divider />
              <ModCategory
                entity={entity}
                project={project}
                category="Demos"
                mods={mods.Demos}
              />
            </>
          ),
        },
      ]}
    />
  );
};
