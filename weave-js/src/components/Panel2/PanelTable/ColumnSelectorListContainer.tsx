import React, {useRef, useState} from 'react';

interface ColumnSelectorListContainerProps {
  onDrop: any;
  visibleColumns: boolean;
}

const ColumnSelectorListContainer: React.FC<ColumnSelectorListContainerProps> =
  React.memo(({onDrop, visibleColumns, children}) => {
    const [dragover, setDragover] = useState(false);
    const selfRef = useRef<HTMLDivElement | null>(null);

    return (
      <div
        ref={selfRef}
        className={
          'column-list-container' +
          (dragover ? ' dragover' : '') +
          (visibleColumns ? ' visible-container' : ' hidden-container')
        }
        onDragStart={() => {
          setDragover(true);
        }}
        onDragEnter={(e: any) => {
          setDragover(true);
        }}
        onDragLeave={(e: any) => {
          if (!selfRef.current!.contains(e.relatedTarget)) {
            setDragover(false);
          }
        }}
        onDragOver={(e: any) => {
          e.preventDefault(); // this is necessary for onDrop to work
        }}
        onDrop={(e: any) => {
          if (
            e.target === selfRef.current ||
            e.target.parentNode === selfRef.current
          ) {
            // only called when dropped on self or on direct child;
            // this prevents propagation from the fields,
            // which are grandchildren
            onDrop();
          }
          setDragover(false);
        }}>
        {children}
      </div>
    );
  });

export default ColumnSelectorListContainer;
