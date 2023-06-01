import * as PanelFileText from '../PanelFileText';

export const inputType = {
  type: 'union' as const,
  members: Object.keys(PanelFileText.EXTENSION_INFO).map(ext => ({
    type: 'list' as const,
    objectType: {
      type: 'file' as const,
      extension: ext,
      wbObjectType: 'none' as const,
    },
  })),
};
