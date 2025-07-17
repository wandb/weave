import {TEAL_600} from '@wandb/weave/common/css/color.styles';
import {Button} from '@wandb/weave/components/Button';
import {WaveLoader} from '@wandb/weave/components/Loaders/WaveLoader';
import {UserLink} from '@wandb/weave/components/UserLink';
import React from 'react';
import {FlexibleXYPlot, Hint, VerticalBarSeries, XAxis, YAxis} from 'react-vis';

export type UserInfo = {
  id: string;
  name?: string;
  photoUrl?: string;
};

export type CostsByUser = {
  user: string;
  totalCost: number;
  callCount: number;
};

export type CostsBarChartProps = {
  project: any;
  widgetConfigs: any[];
  setWidgetConfigs: (configs: any[]) => void;
  costsData: CostsByUser[];
  isLoading: boolean;
  userInfo: UserInfo[];
};

const CostsBarChart: React.FC<CostsBarChartProps> = ({
  project,
  widgetConfigs,
  setWidgetConfigs,
  costsData,
  isLoading,
  userInfo,
}) => {
  const [isFullscreen, setIsFullscreen] = React.useState(false);
  const [isChartHovered, setIsChartHovered] = React.useState(false);
  const [hintValue, setHintValue] = React.useState<any>(null);
  const chartHeight = isFullscreen ? window.innerHeight : 232;
  const chartWidth = isFullscreen ? window.innerWidth : 'calc(100% - 8px)';

  // Prepare data for react-vis
  const barData = costsData.map(d => ({
    x: d.user,
    y: d.totalCost,
    callCount: d.callCount,
  }));

  const chartContent = (
    <div
      style={{
        border: '1px solid #e0e0e0',
        borderRadius: 6,
        background: '#fff',
        display: 'flex',
        flexDirection: 'column',
        height: chartHeight,
        width: chartWidth || '100%',
        minHeight: 0,
        boxShadow: '0 1px 4px rgba(0,0,0,0.03)',
        overflow: 'hidden',
        zIndex: isFullscreen ? 1001 : 'auto',
        flexShrink: 0,
      }}
      onMouseEnter={() => setIsChartHovered(true)}
      onMouseLeave={() => setIsChartHovered(false)}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontWeight: 500,
          userSelect: 'none',
          position: 'relative',
          height: 32,
          flex: '0 0 auto',
        }}>
        <div
          style={{
            position: 'absolute',
            left: 0,
            right: 0,
            top: 0,
            bottom: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            pointerEvents: 'none',
            zIndex: 0,
          }}>
          <span
            style={{
              fontWeight: 600,
              fontSize: isFullscreen ? 20 : 13,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              pointerEvents: 'none',
              maxWidth: 'calc(100% - 60px)',
            }}>
            Costs by User
          </span>
        </div>
        <div
          style={{
            display: 'flex',
            gap: 2,
            flex: '0 0 auto',
            zIndex: 1,
            marginLeft: 'auto',
            marginRight: isFullscreen ? 8 : 4,
            marginTop: isFullscreen ? 24 : 0,
            opacity: isChartHovered || isFullscreen ? 1 : 0,
            transition: 'opacity 0.2s ease-in-out',
          }}>
          <Button
            className="no-drag"
            icon="close"
            variant="ghost"
            size="small"
            onClick={() => {
              setWidgetConfigs(
                widgetConfigs.filter(c => c.type !== 'costsBarChart')
              );
            }}
          />
        </div>
      </div>
      {isLoading ? (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
            minHeight: 200,
          }}>
          <WaveLoader size="small" />
        </div>
      ) : barData.length === 0 ? (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
            color: '#8F8F8F',
            fontSize: '14px',
          }}>
          No cost data could be found
        </div>
      ) : (
        <div style={{flex: 1, minHeight: 40, minWidth: 40}}>
          <FlexibleXYPlot
            xType="ordinal"
            margin={{left: 60, right: 20, top: 20, bottom: 60}}
            onMouseLeave={() => setHintValue(null)}>
            <XAxis
              tickLabelAngle={0}
              tickFormat={(userId: string) => {
                const user = (userInfo ?? []).find(u => u.id === userId);
                return user ? user.name ?? userId : userId;
              }}
            />
            <YAxis tickFormat={(value: number) => `$${value.toFixed(2)}`} />
            <VerticalBarSeries
              data={barData}
              color={TEAL_600}
              barWidth={0.8}
              onValueMouseOver={v => setHintValue(v)}
              onValueMouseOut={() => setHintValue(null)}
            />
            {hintValue && (
              <Hint value={hintValue}>
                <div
                  style={{
                    background: '#fff',
                    border: '1px solid #ccc',
                    padding: 8,
                    borderRadius: 4,
                    fontSize: 12,
                  }}>
                  <div>
                    <b>User:</b>{' '}
                    {hintValue.x ? (
                      <UserLink userId={hintValue.x} includeName={true} />
                    ) : (
                      hintValue.x
                    )}
                  </div>
                  <div>
                    <b>Total Cost:</b> ${hintValue.y.toFixed(4)}
                  </div>
                  <div>
                    <b>Calls:</b> {hintValue.callCount}
                  </div>
                </div>
              </Hint>
            )}
          </FlexibleXYPlot>
        </div>
      )}
    </div>
  );

  if (isFullscreen) {
    return (
      <div
        style={{
          position: 'fixed',
          top: 40,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.8)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
        }}
        onClick={e => {
          if (e.target === e.currentTarget) {
            setIsFullscreen(false);
          }
        }}>
        {chartContent}
      </div>
    );
  }

  return chartContent;
};

export default CostsBarChart;
