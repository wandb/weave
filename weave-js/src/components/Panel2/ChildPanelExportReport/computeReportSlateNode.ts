import {voidNode} from '@wandb/weave/core';
import {v4 as uuid} from 'uuid';
import {ChildPanelFullConfig} from '../ChildPanel';
import {getConfigForPath} from '../panelTree';
import {toWeaveType} from '../toWeaveType';

type WeavePanelSlateNode = {
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
  const inputNodeVal = {
    id: 'Group',
    input_node: voidNode(),
    config: {
      items: {
        panel: targetConfig,
      },
      disableDeletePanel: true,
      enableAddPanel: true, // actually means "is editable"
      layoutMode: 'vertical',
      showExpressions: true,
    },
    vars: {},
  };

  return {
    type: 'weave-panel',
    children: [{text: ''}],
    config: {
      isWeave1Panel: true,
      panelConfig: {
        id: 'Panel',
        config: {
          documentId: uuid(),
        },
        input_node: {
          nodeType: 'const',
          type: toWeaveType(inputNodeVal),
          val: inputNodeVal,
        },
        vars: {},
      },
    },
  };
};
