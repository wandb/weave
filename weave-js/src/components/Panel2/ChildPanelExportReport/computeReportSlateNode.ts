import {ID} from '@wandb/weave/core';
import {ChildPanelFullConfig} from '../ChildPanel';
import {getConfigForPath, makeGroup, makePanel} from '../panelTree';
import {toWeaveType} from '../toWeaveType';

export type WeavePanelSlateNode = {
  type: 'weave-panel';
  /**
   * A weave-panel slate node in a report is a "void element", which
   * requires an empty child text node. See:
   * https://docs.slatejs.org/api/nodes/element#rendering-void-elements
   */
  children: [{text: ''}];
  /** Slate node config, passed to RootQueryPanel in core */
  config: {
    isWeave1Panel: true;
    /** Packaged PanelPanel config */
    panelConfig: ChildPanelFullConfig<{
      /**
       * Unique documentId is required because multiple
       * panels could be exported to the same report.
       */
      documentId: string;
    }>;
  };
};

/**
 * Given a full child panel config and the path to a target panel,
 * get the target config and map it into a slate node that can be
 * displayed in a report
 *
 * @param fullConfig - config containing the target panel
 * @param targetPath - path to the target panel
 */
export const computeReportSlateNode = (
  fullConfig: ChildPanelFullConfig,
  targetPath: string[]
): WeavePanelSlateNode => {
  const targetConfig = getConfigForPath(fullConfig, targetPath);
  const inputNodeVal = makeGroup(
    {
      panel: targetConfig,
    },
    {
      disableDeletePanel: true,
      enableAddPanel: true, // actually means "is editable"
      layoutMode: 'vertical',
    }
  );

  return {
    type: 'weave-panel',
    children: [{text: ''}],
    config: {
      isWeave1Panel: true,
      panelConfig: makePanel(
        'Panel',
        {
          documentId: ID(12),
        },
        {
          nodeType: 'const',
          type: toWeaveType(inputNodeVal),
          val: inputNodeVal,
        }
      ),
    },
  };
};
