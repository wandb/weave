import {
  gotoBlankDashboard,
  panelTypeInputExpr,
  addSidebarPanel,
  scrollToEEAndType,
  panelChangeId,
  tableAppendColumn,
  tableCheckContainsValue,
  addMainPanel,
} from '../testlib';

describe('dashboard', () => {
  it('dashboard', () => {
    gotoBlankDashboard();

    // Setup sidebar
    panelTypeInputExpr(['sidebar', 'var0'], 'range(0, 100, 1)');
    addSidebarPanel();
    panelTypeInputExpr(['sidebar', 'var1'], '2.5');
    addSidebarPanel();
    panelTypeInputExpr(['sidebar', 'var2'], 'var1');
    // dashboardConvertToControl(['sidebar', 'var2']);

    // Add table panel
    scrollToEEAndType(['main', 'panel0'], 'var0');
    panelChangeId(['main', 'panel0'], 'table');
    tableAppendColumn(['main', 'panel0'], 'row ** var1');
    tableCheckContainsValue(['main', 'panel0'], '5.657');

    // Add another table panel
    addMainPanel();
    scrollToEEAndType(['main', 'panel1'], 'panel0.all_rows');
    tableCheckContainsValue(['main', 'panel1'], '5.657');

    // Add plot panel
    addMainPanel();
    scrollToEEAndType(['main', 'panel2'], 'panel0.all_rows');
    panelChangeId(['main', 'panel2'], 'plot');

    // sliderSetValue(['sidebar', 'var2'], 0.5);
    panelTypeInputExpr(['sidebar', 'var1'], '0.5');
    tableCheckContainsValue(['main', 'panel0'], '1.414');
    tableCheckContainsValue(['main', 'panel1'], '1.414');
  });
});
