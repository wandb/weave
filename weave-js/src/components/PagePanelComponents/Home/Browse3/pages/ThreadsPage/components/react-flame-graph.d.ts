declare module 'react-flame-graph' {
  export interface FlameGraphNode {
    name: string;
    value: number;
    children?: FlameGraphNode[];
    color?: string;
    backgroundColor?: string;
    timing?: {
      start: number;
      end: number;
    };
  }

  export interface FlameGraphProps {
    data: FlameGraphNode;
    height: number;
    width: number | string;
    onChange?: (node: FlameGraphNode) => void;
    disableHover?: boolean;
    style?: React.CSSProperties;
    className?: string;
  }

  export const FlameGraph: React.FC<FlameGraphProps>;
} 