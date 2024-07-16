/**
 * This component determines how many children it can show.
 */

import _ from 'lodash';
import React, {isValidElement, ReactChild, useEffect, useState} from 'react';
import ReactDOM from 'react-dom';

import {useDeepMemo} from '../../../../../hookUtils';

type VariableChildrenDisplayProps = {
  children: ReactChild[];
  width: number;
  gap?: number;
};

const indexOfLargest = (numbers: Array<number | null>): number => {
  if (numbers.length === 0) {
    return -1;
  }

  let largestIndex: number | null = null;
  let largestValue: number | null = null;

  for (let i = 0; i < numbers.length; i++) {
    const currentValue = numbers[i];

    if (
      currentValue !== null &&
      (largestValue === null || currentValue >= largestValue)
    ) {
      largestValue = currentValue;
      largestIndex = i;
    }
  }

  return largestIndex ?? -1;
};

// const measureWidth = (node: ReactChild): Promise<number> => {
//   return measureWidths([node]).then(([width]) => width);
// };
const measureWidths = (nodes: ReactChild[]): Promise<number[]> => {
  // Create a container to render the nodes
  const container = document.createElement('div');
  container.style.position = 'absolute';
  container.style.top = '0';
  container.style.left = '0';
  container.style.visibility = 'hidden';
  container.style.height = 'auto';
  container.style.width = 'auto';
  container.style.whiteSpace = 'nowrap';

  document.body.appendChild(container);

  const widthPromises: Array<Promise<number>> = nodes.map(node => {
    return new Promise(resolve => {
      const wrapper = document.createElement('div');

      // Append the wrapper to the container
      container.appendChild(wrapper);

      // Render the node and measure its width
      if (React.isValidElement(node)) {
        ReactDOM.render(node, wrapper, () => {
          const width = wrapper.offsetWidth;
          resolve(width);

          // Clean up after measuring
          ReactDOM.unmountComponentAtNode(wrapper);
          container.removeChild(wrapper);
        });
      } else {
        wrapper.textContent = node.toString();
        const width = wrapper.offsetWidth;
        resolve(width);
        container.removeChild(wrapper);
      }
    });
  });

  // Clean up the container once all measurements are done
  return Promise.all(widthPromises).then(widths => {
    document.body.removeChild(container);
    return widths;
  });
};

/**
 * Compare two React nodes for equality.
 */
const isEqualNode = (
  node1: React.ReactNode,
  node2: React.ReactNode
): boolean => {
  if (!isValidElement(node1) || !isValidElement(node2)) {
    return node1 === node2;
  }

  if (node1.type !== node2.type) {
    return false;
  }

  const props1 = {...node1.props, children: undefined};
  const props2 = {...node2.props, children: undefined};

  if (JSON.stringify(props1) !== JSON.stringify(props2)) {
    return false;
  }

  const children1 = React.Children.toArray(node1.props.children);
  const children2 = React.Children.toArray(node2.props.children);

  if (children1.length !== children2.length) {
    return false;
  }

  for (let i = 0; i < children1.length; i++) {
    if (!isEqualNode(children1[i], children2[i])) {
      return false;
    }
  }

  return true;
};

const isEqualNodeArray = (
  nodes1: React.ReactNode[],
  nodes2: React.ReactNode[] | undefined
) => {
  if (nodes2 === undefined) {
    return false;
  }
  if (nodes1.length !== nodes2.length) {
    return false;
  }
  for (let i = 0; i < nodes1.length; i++) {
    if (!isEqualNode(nodes1[i], nodes2[i])) {
      return false;
    }
  }
  return true;
};

const sumSize = (sizes: Array<number | null>, gapWidth: number) => {
  const included = sizes.filter(size => size !== null) as number[];
  const gapSum = Math.max(0, gapWidth * (included.length - 1));
  return _.sum(included) + gapSum;
};

const calculateDisplayedItems = (
  availableWidth: number,
  childWidths: number[],
  gap: number,
  extraSize: number
) => {
  const result: Array<number | null> = _.clone(childWidths);
  let used = sumSize(childWidths, gap);
  if (used < availableWidth) {
    return result;
  }

  // Not enough room to display everything
  availableWidth -= extraSize;
  while (used > availableWidth) {
    console.log({result, used, availableWidth});
    const largestIndex = indexOfLargest(result);
    console.log({largestIndex});
    if (largestIndex === -1) {
      return _.fill(Array(result.length), null);
    }
    result[largestIndex] = null;
    used = sumSize(result, gap);
  }
  return result;
};

export const VariableChildrenDisplay = ({
  children,
  width,
  gap = 0,
}: VariableChildrenDisplayProps) => {
  const [childWidths, setChildWidths] = useState<number[]>([]);
  const memoedChildren = useDeepMemo(children, isEqualNodeArray);

  useEffect(() => {
    measureWidths(memoedChildren).then(setChildWidths);
  }, [memoedChildren]);

  const displayedItems = calculateDisplayedItems(width, childWidths, gap, 50);
  const numChildren = memoedChildren.length;
  const numShown = displayedItems.filter(item => item !== null).length;
  const numHidden = numChildren - numShown;

  console.log({memoedChildren, childWidths, displayedItems, width});

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap,
        overflow: 'hidden',
      }}>
      {memoedChildren.map((child, index) => {
        if (displayedItems[index] === null) {
          return null;
        }
        return <div key={index}>{child}</div>;
      })}
      {numChildren && numChildren === numHidden ? (
        <span>({numChildren})</span>
      ) : numHidden > 0 ? (
        <div className="whitespace-nowrap">{numHidden} more</div>
      ) : null}
    </div>
  );
};
