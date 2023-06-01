import {Client, Weave} from '@wandb/weave/core';

import {PanelSpec} from './components/Panel2/panel';

// TODO (ts): move this implementation should be in the cg package
export class WeaveApp extends Weave {
  private readonly panelSpecs: PanelSpec[];

  constructor(readonly client: Client) {
    super(client);
    this.panelSpecs = [];
  }

  // Panel-related
  panel(id: string) {
    const panel = this.panelSpecs.find(spec => spec.id === id);
    if (panel == null) {
      throw new Error(`Cannot find panel with id "${id}"`);
    }
    return panel;
  }
}
