// Used for linking from Weave UI to W&B UI.
// Note that dev Weave will point to prod app.
export const urlWandbFrontend = () => {
  const base = window.WEAVE_CONFIG.WANDB_BASE_URL;
  if (base === 'https://api.wandb.ai') {
    return 'https://wandb.ai';
  }
  return base;
};
