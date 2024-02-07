import {
  gotoBlankDashboard,
  panelTypeInputExpr,
  scrollToEEAndType,
  panelChangeId,
  getPanel,
  openPanelConfig,
  setPlotConfig,
  switchToExpressionEditor,
} from '../testlib';

describe('plotboard', () => {
  it('configure plot panel', () => {
    gotoBlankDashboard();

    // Setup sidebar
    panelTypeInputExpr(['sidebar', 'var0'], 'range(0, 1000, 1)');

    // Add table panel
    scrollToEEAndType(['main', 'panel0'], 'var0');

    // Make it a plot
    panelChangeId(['main', 'panel0'], 'plot');

    const panel = getPanel(['main', 'panel0']);
    const configPanel = openPanelConfig(panel);

    let xDimConfig = configPanel.get('[data-test="x-dim-config"]');
    switchToExpressionEditor(xDimConfig);
    // Not sure why switchToExpressionEditor affects its argument, but it does
    xDimConfig = configPanel.get('[data-test="x-dim-config"]');
    setPlotConfig(xDimConfig, 'row');

    let yDimConfig = configPanel.get('[data-test="y-dim-config"]');
    switchToExpressionEditor(yDimConfig);
    yDimConfig = configPanel.get('[data-test="y-dim-config"]');
    setPlotConfig(yDimConfig, 'sin(row / 31.4159)');

    let colorDimConfig = configPanel.get('[data-test="label-dim-config"]');
    switchToExpressionEditor(colorDimConfig);
    colorDimConfig = configPanel.get('[data-test="label-dim-config"]');
    setPlotConfig(colorDimConfig, 'row');

    ['line', 'bar'].forEach(mark => {
      cy.get('[data-testid="dropdown-mark"]').click().contains(mark).click();
      [20, 40, 60, 80, 100, 120, 150, 175, 200, 220].forEach(x => {
        setPlotConfig(
          configPanel.get('[data-test="label-dim-config"]'),
          `row % ${x}`
        );
        cy.wait(200);
      });
    });
  });
});
