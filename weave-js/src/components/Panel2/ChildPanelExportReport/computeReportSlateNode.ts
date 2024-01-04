import {
  ID,
  isAssignableTo,
  isConstNode,
  isNonVoidNode,
  isVarNode,
} from '@wandb/weave/core';
import _ from 'lodash';

import {weaveTypeIsPanel} from '../../PagePanelComponents/util';
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
 * Naive implementation to find all the variable references in an object.
 * Ideally we would have a more structured way to walk the object, but it
 * is not obvious to me how we can do this for any arbitrary panel/variable
 * since the config might contain variables at any level of nesting.
 */
const getVarNamesForObj = (obj: any) => {
  const names: string[] = [];
  if (isVarNode(obj)) {
    names.push(obj.varName);
  }
  if (obj && typeof obj === 'object') {
    Object.values(obj).forEach((val: any) => {
      if (typeof val === 'object') {
        names.push(...getVarNamesForObj(val));
      }
    });
  }

  return names;
};

/**
 * Returns the minimal set of dependent variables as a dictionary of panels.
 */
const getVarItemsForPath = (
  fullConfig: ChildPanelFullConfig,
  targetConfig: ChildPanelFullConfig
): Record<string, ChildPanelFullConfig> => {
  const varItems: Record<string, ChildPanelFullConfig> = {};

  // First, extract the stack for a given panel.
  mapPanels(fullConfig, [], (config, stack) => {
    if (
      // mapPanels does not guarantee reference equality, so we need to use
      // _.isEqual to compare the configs. This is at least the case for Group
      // panels, which are cloned in mapPanels.
      _.isEqual(config, targetConfig) ||
      // Additionally, the target config might be a direct node itself, so we
      // need to also check for equality with the input_node of the target
      // config.
      (isNonVoidNode(targetConfig) &&
        _.isEqual(config.input_node, targetConfig))
    ) {
      stack.forEach(frame => {
        if (isConstNode(frame.value) && weaveTypeIsPanel(frame.value.type)) {
          if (!isAssignableTo(frame.value.type, {type: 'Group' as any})) {
            varItems[frame.name] = frame.value.val;
          } else {
            // Skip groups - their children will make it in later
          }
        } else {
          varItems[frame.name] = makePanel(
            'Expression',
            undefined,
            frame.value
          );
        }
      });
    }
    return config;
  });

  // Next, filter out only the needed variables (assumes no duplicate var names)
  const configQueue = [targetConfig];
  const addedNames: string[] = [];
  const filteredVarItems: Record<string, ChildPanelFullConfig> = {};

  while (configQueue.length > 0) {
    const config = configQueue.shift();
    const names = getVarNamesForObj(config);
    Object.entries(varItems).forEach(([name, item]) => {
      if (!addedNames.includes(name) && names.includes(name)) {
        configQueue.push(item);
        addedNames.push(name);
      }
    });
  }

  // Reverse the order so that the variables are in the order they are
  // defined in the dashboard
  addedNames.reverse().forEach(name => {
    filteredVarItems[name] = varItems[name];
  });

  return filteredVarItems;
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
  const targetPanelName = targetPath[targetPath.length - 1];
  const varItems = getVarItemsForPath(fullConfig, targetConfig);
  const hasVars = Object.keys(varItems).length > 0;
  const varsConfig = hasVars
    ? makeGroup(varItems, {
        childNameBase: 'var',
        layoutMode: 'vertical',
      })
    : undefined;

  const packagedGroup = makeGroup(
    {
      vars: varsConfig,
      [targetPanelName]: targetConfig,
    },
    {
      disableDeletePanel: true,
      enableAddPanel: true, // actually means "is editable"
      equalSize: true,
      isNumItemsLocked: true,
      layoutMode: 'vertical',
      panelInfo: {
        vars: {
          hidden: true,
        },
        [targetPanelName]: {
          controlBar: 'editable',
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
          type: toWeaveType(packagedGroup),
          val: packagedGroup,
        }
      ),
    },
  };
};
