declare module 'react-flame-graph' {
  export interface FlameGraphNode {
    id: string;
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
    onChange?: (node: {source: FlameGraphNode}) => void;
    disableHover?: boolean;
    style?: React.CSSProperties;
    className?: string;
  }

  export const FlameGraph: React.FC<FlameGraphProps>;
}
