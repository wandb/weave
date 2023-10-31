import {ID, dereferenceAllVars} from '@wandb/weave/core';
import {ChildPanelFullConfig} from '../ChildPanel';
import {getConfigForPath, makeGroup, makePanel, mapPanels} from '../panelTree';
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

  const varsItems: Record<string, ChildPanelFullConfig> = {};
  // perf: need func that just gets stack for target instead of map over full config
  mapPanels(fullConfig, [], (config, stack) => {
    if (config === targetConfig) {
      const {usedStack} = dereferenceAllVars(config.input_node, stack);
      // issue: usedStack doesn't include tables & plots
      usedStack.forEach(frame => {
        varsItems[frame.name] = makePanel(
          'Expression', // issue: not all vars are expressions
          undefined,
          frame.value
        );
      });
    }
    return config;
  });

  const inputNodeVal = makeGroup(
    {
      // NOTE: order matters! `vars` must come before `panel`
      vars: makeGroup(varsItems, {
        allowedPanels: ['Expression'], // issue: again, not all vars are expressions
        childNameBase: 'var',
        layoutMode: 'vertical',
      }),
      panel: targetConfig,
    },
    {
      disableDeletePanel: true,
      enableAddPanel: true, // actually means "is editable"
      equalSize: true,
      layoutMode: 'vertical',
      panelInfo: {
        vars: {
          hidden: true,
        },
      },
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
