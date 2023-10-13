import {
  gotoBlankDashboard,
  panelTypeInputExpr,
  scrollToEEAndType,
  panelChangeId,
  getPanel,
  openPanelConfig,
  setPlotConfig,
} from '../testlib';

describe('plotboard', () => {
  it('dashboard: multi series', () => {
    gotoBlankDashboard();

    // Setup sidebar
    panelTypeInputExpr(['sidebar', 'var0'], 'range(0, 1000, 1)');

    // Add table panel
    scrollToEEAndType(['main', 'panel0'], 'var0');

    // Make it a plot
    panelChangeId(['main', 'panel0'], 'plot');

    const panel = getPanel(['main', 'panel0']);
    const configPanel = openPanelConfig(panel);

    const xDimConfig = configPanel.get('[data-test="x-dim-config"]');
    setPlotConfig(xDimConfig, 'row');

    const yDimConfig = configPanel.get('[data-test="y-dim-config"]');
    setPlotConfig(yDimConfig, 'sin(row / 31.4159)');

    const colorDimConfig = configPanel.get('[data-test="label-dim-config"]');
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

    /*
        panelChangeId(['main', 'panel0'], 'plot');
        tableAppendColumn(['main', 'panel0'], 'row ** var1');
        tableCheckContainsValue(['main', 'panel0'], '5.657');
    
        // Add another table panel
        addMainPanel();
        scrollToEEAndType(['main', 'panel1'], 'panel0.all_rows');
        tableCheckContainsValue(['main', 'panel1'], '5.657');
    
        // Add plot panel
        addMainPanel();
        scrollToEEAndType(['main', 'panel2'], 'panel0.all_rows');
    
        // sliderSetValue(['sidebar', 'var2'], 0.5);
        panelTypeInputExpr(['sidebar', 'var1'], '0.5');
        tableCheckContainsValue(['main', 'panel0'], '1.414');
        tableCheckContainsValue(['main', 'panel1'], '1.414');
        */
  });
});
