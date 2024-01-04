import React from 'react';

import {Alert} from '../Alert';

// This is a merge of 4 files from app.

export function scrollIntoBounds(
  rect: DOMRect,
  minSpaceFromTop: number,
  minSpaceFromBottom: number
) {
  // scroll into bounds if necessary
  if (rect.top < minSpaceFromTop) {
    window.scrollBy({
      top: rect.top - minSpaceFromTop,
      behavior: 'smooth',
    });
  }
  if (rect.bottom > window.innerHeight - minSpaceFromBottom) {
    window.scrollBy({
      top: rect.bottom - (window.innerHeight - minSpaceFromBottom),
      behavior: 'smooth',
    });
  }
}

/**
 * Dims the whole screen aside from the desired element.
 * @param el The element to focus on.
 * @param options
 */
export const flashFocus = (
  el: Element,
  options?: {
    width?: number;
    height?: number;
    padding?: number;
    borderRadius?: number;
    minSpaceFromTop?: number;
    minSpaceFromBottom?: number;
    offsetX?: number;
    offsetY?: number;
    popping?: boolean;
  }
) => {
  const existingFocuser = document.body.querySelector('.focuser');
  if (existingFocuser) {
    return;
  }

  const rect = el.getBoundingClientRect();

  const minSpaceFromTop = options?.minSpaceFromTop ?? 0;
  const minSpaceFromBottom = options?.minSpaceFromBottom ?? 0;
  let width = options?.width ?? rect.width;
  let height = options?.height ?? rect.height;
  const padding = options?.padding ?? 8;
  width += padding * 2;
  height += padding * 2;
  const borderRadius = options?.borderRadius ?? 4;
  const offsetX = options?.offsetX ?? 0;
  const offsetY = options?.offsetY ?? 0;
  const popping = options?.popping ?? false;

  const scrollLeft = window.pageXOffset || document.documentElement.scrollLeft;
  const scrollTop = window.pageYOffset || document.documentElement.scrollTop;

  const focuser = document.createElement('div');
  focuser.className = 'focuser';
  focuser.style.left = `${rect.left + offsetX - padding + scrollLeft}px`;
  focuser.style.top = `${rect.top + offsetY - padding + scrollTop}px`;
  focuser.style.width = `${width}px`;
  focuser.style.height = `${height}px`;
  focuser.style.borderRadius = `${borderRadius}px`;
  document.body.appendChild(focuser);

  scrollIntoBounds(rect, minSpaceFromTop, minSpaceFromBottom);

  const removeFocuser = () => {
    focuser.classList.add('fading-out');
    window.setTimeout(() => {
      if (document.body.contains(focuser)) {
        document.body.removeChild(focuser);
      }
    }, 400);
    window.removeEventListener('mousedown', removeFocuser);
  };

  window.addEventListener('mousedown', removeFocuser);

  const pop = () => {
    focuser.classList.add('popping');
    el.removeEventListener('mousedown', pop);
  };

  if (popping) {
    el.addEventListener('mousedown', pop);
  }
};

interface EmptyVisualizationsProps {
  headerText?: string;
  helpText?: string | JSX.Element;
}

export const EmptyVisualizations = (props: EmptyVisualizationsProps) => {
  return (
    <div style={{padding: '8px 32px'}}>
      <Alert severity="info">
        Click the "New panel" button to start building a board.
      </Alert>
    </div>
    // <EmptyWatermark
    //   className="empty-watermark-visualizations"
    //   // imageSource={emptyImg}
    //   // imageSource2x={emptyImg2x}
    //   header={props.headerText || 'No visualizations yet.'}
    //   details={
    //     props.helpText ||
    //     "Add visual components to illustrate the runs from this section's data."
    //   }
    //   wide
    // />
  );
};

const EmptyPanelBankSectionWatermark = () => {
  return (
    <EmptyVisualizations
      headerText="No visualizations in this section."
      helpText={
        <div style={{display: 'flex', alignItems: 'center'}}>
          <div style={{marginRight: 4}}>
            <span className="hide-in-report">Drag a panel here, or </span>
            <span
              className="add-vis-helper underline-dashed"
              onClick={(e: React.MouseEvent) => {
                const el = (
                  e.currentTarget.closest('.panel-bank__section') ||
                  e.currentTarget.closest('.report-section')
                )?.querySelector('.add-vis-button');
                if (el) {
                  flashFocus(el, {
                    minSpaceFromTop: 60,
                    padding: 3,
                    popping: true,
                  });
                }
              }}>
              add a visualization
            </span>
            .
          </div>
        </div>
      }
    />
  );
};

export default EmptyPanelBankSectionWatermark;
