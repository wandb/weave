import React from 'react'
import ReactDOM from 'react-dom'
import Measure from 'react-measure'

import * as S from './WBPopup.styles'

const VERTICAL_MARGIN = 2
const HORIZONTAL_MARGIN = 16

export type WBPopupDirection =
  | 'top left'
  | 'top center'
  | 'top right'
  | 'center left'
  | 'center right'
  | 'bottom left'
  | 'bottom center'
  | 'bottom right'

export type WBPopupProps = {
  className?: string
  style?: React.CSSProperties
  x: number
  y: number
  // setting an explicit maxHeight disables expansion on scroll
  maxHeight?: number
  direction?: WBPopupDirection
  // setting this makes x, y, and direction determine the positioning
  // of the provided child element rather than the whole popup.
  elementToPosition?: HTMLElement | null
  noPortal?: boolean
  scrollerRef?: React.Ref<HTMLDivElement>
  onScroll?: (event: React.UIEvent<HTMLDivElement, UIEvent>) => void
  children: React.ReactNode
}

export const WBPopup = React.forwardRef<HTMLDivElement, WBPopupProps>(
  (
    {
      className,
      style,
      x,
      y,
      direction,
      elementToPosition,
      noPortal,
      scrollerRef,
      maxHeight: propsMaxHeight,
      onScroll,
      children
    },
    ref
  ) => {
    const appliedDirection = direction ?? 'bottom center'
    const [scrollerElement, setScrollerElement] =
      React.useState<HTMLDivElement | null>(null)
    const [height, setHeight] = React.useState(0)
    const [top, setTop] = React.useState(0)
    const [left, setLeft] = React.useState(0)
    const [contentHeight, setContentHeight] = React.useState(0)
    const maxHeight = propsMaxHeight ?? window.innerHeight - 2 * VERTICAL_MARGIN
    React.useLayoutEffect(() => {
      if (scrollerElement == null) {
        return
      }
      const [verticalDirection, horizontalDirection] =
        appliedDirection.split(' ')
      const anchorWidth = elementToPosition
        ? elementToPosition.offsetWidth
        : scrollerElement.offsetWidth
      const anchorHeight = elementToPosition
        ? elementToPosition.offsetHeight
        : contentHeight

      let adjustedY = y
      if (elementToPosition) {
        adjustedY -= elementToPosition.offsetTop
      }
      switch (verticalDirection) {
        case 'top':
          adjustedY -= anchorHeight
          break
        case 'center':
          adjustedY -= anchorHeight / 2
          break
        case 'bottom':
          break
      }

      let adjustedX = x
      if (elementToPosition) {
        adjustedX -= elementToPosition.offsetLeft
      }
      switch (horizontalDirection) {
        case 'left':
          adjustedX -= anchorWidth
          break
        case 'center':
          adjustedX -= anchorWidth / 2
          break
        case 'right':
          break
      }

      let cutTop = 0
      if (adjustedY < VERTICAL_MARGIN) {
        cutTop = VERTICAL_MARGIN - adjustedY
      }
      const newTop = Math.max(VERTICAL_MARGIN, adjustedY)
      setTop(newTop)
      setHeight(
        Math.min(
          contentHeight - cutTop,
          window.innerHeight - VERTICAL_MARGIN - newTop,
          maxHeight
        )
      )
      // this condition prevents snapping back
      // whenever the popup moves
      if (cutTop > scrollerElement.scrollTop) {
        scrollerElement.scrollTo({ top: cutTop })
      }
      setLeft(
        Math.max(
          Math.min(
            adjustedX,
            window.innerWidth - HORIZONTAL_MARGIN - scrollerElement.offsetWidth
          ),
          HORIZONTAL_MARGIN
        )
      )
    }, [
      scrollerElement,
      x,
      y,
      appliedDirection,
      elementToPosition,
      maxHeight,
      contentHeight
    ])

    const scrollerCallbackRef = React.useCallback(
      (node: HTMLDivElement | null) => {
        if (scrollerRef) {
          if (typeof scrollerRef === 'function') {
            scrollerRef(node)
          } else {
            ;(scrollerRef as any).current = node
          }
        }
        setScrollerElement(node)
      },
      [scrollerRef]
    )

    const content = (
      <S.Wrapper
        ref={ref}
        left={left}
        height={Math.max(height, 0)}
        top={top}
        className={className}
        style={style}
      >
        <Measure
          bounds
          onResize={({ bounds }) => {
            setContentHeight(bounds?.height || 0)
          }}
        >
          {({ measureRef }) => {
            return (
              <S.Scroller
                ref={scrollerCallbackRef}
                contentOverflows={contentHeight > height}
                onScroll={e => {
                  onScroll?.(e)
                  if (propsMaxHeight || height >= maxHeight) {
                    return
                  }
                  if (top === VERTICAL_MARGIN) {
                    // scrolling up
                    const previousScrollTop =
                      e.currentTarget.scrollHeight -
                      e.currentTarget.offsetHeight
                    const scrollDist = Math.min(
                      previousScrollTop - e.currentTarget.scrollTop,
                      window.innerHeight - VERTICAL_MARGIN - top
                    )
                    setHeight(height + scrollDist)
                    e.currentTarget.scrollTo({
                      top: e.currentTarget.scrollHeight
                    })
                  } else {
                    // scrolling down
                    const scrollDist = Math.min(
                      e.currentTarget.scrollTop,
                      top - VERTICAL_MARGIN
                    )
                    setHeight(height + scrollDist)
                    setTop(top - scrollDist)
                    e.currentTarget.scrollTo({ top: 0 })
                  }
                }}
              >
                <div ref={measureRef}>{children}</div>
              </S.Scroller>
            )
          }}
        </Measure>
      </S.Wrapper>
    )

    return noPortal ? content : ReactDOM.createPortal(content, document.body)
  }
)
