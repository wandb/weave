import promisify from 'cypress-promise';
import {exec} from '../testlib';

const gotoBlankDashboard = async () => {
  await promisify(exec('python cypress/e2e/interactive/blank.py', 10000));
  // const url = result.stdout;
  // E.g. for devmode
  const url =
    '/?fullScreen&expNode=%7B%22nodeType%22%3A%20%22output%22%2C%20%22type%22%3A%20%22any%22%2C%20%22fromOp%22%3A%20%7B%22name%22%3A%20%22get%22%2C%20%22inputs%22%3A%20%7B%22uri%22%3A%20%7B%22nodeType%22%3A%20%22const%22%2C%20%22type%22%3A%20%22string%22%2C%20%22val%22%3A%20%22local-artifact%3A///dashboard-list%3Alatest/obj%22%7D%7D%7D%7D';
  cy.viewport(1600, 900);
  cy.visit(url);
  cy.get('canvas').should('be.visible');
  cy.get('[data-testid="header-center-controls"]').should('be.visible').click();
  cy.get('[data-testid="new-board-button"]').should('be.visible').click();
};

const addSidebarPanel = () => {
  getPanel(['sidebar']).find('button').contains('Add var').click();
};

const addMainPanel = () => {
  getPanel(['main']).find('button').contains('+').click({force: true});
};

const dashboardConvertToControl = (path: string[]) => {
  const panel = getPanel(path);
  panel.find('i.sliders').click();
};

const getPanel = (path: string[]) => {
  const attrPath = path.map(p => `[data-weavepath=${p}]`);
  return cy.get(attrPath.join(' '));
};

const panelTypeInputExpr = (path: string[], text: string) => {
  const panel = getPanel(path);
  panel
    .find('[data-test=expression-editor-container] [contenteditable=true]')
    .click()
    .type(text)
    .wait(300)
    .type('{enter}', {force: true});
};

const panelChangeId = (path: string[], text: string) => {
  const panel = getPanel(path);
  panel.find('[data-test-comp=PanelNameEditor] [contenteditable=true]').click();
  cy.get('[data-test=wb-menu-item]').contains(text).click();
};

const tableAppendColumn = (path: string[], expr) => {
  const panel = getPanel(path);
  panel.find('i.column-actions-trigger').click({force: true});
  // TODO: these should be panel.find... but that didn't work on my first try
  cy.get('[data-test=wb-menu-item]').contains('Insert 1 right').click();
  cy.get('[data-test=column-header').last().click();

  cy.get('.wb-table-action-popup')
    .find('[data-test=expression-editor-container] [contenteditable=true]')
    .click()
    .type('{backspace}{backspace}{backspace}{backspace}{backspace}')
    .type(expr);
  cy.get('#root').click({force: true});
};

const tableCheckContainsValue = (path: string[], value: string) => {
  const panel = getPanel(path);
  panel.find('.BaseTable__row-cell div').contains(value);
};

const sliderSetValue = (path: string[], value: number) => {
  const panel = getPanel(path);
  panel.find('input[type=range]').invoke('val', value).trigger('input');
};

describe('dashboard', () => {
  it('dashboard', async () => {
    await gotoBlankDashboard();

    // Setup sidebar
    panelTypeInputExpr(['sidebar', 'var0'], 'range(0, 100, 1)');
    addSidebarPanel();
    panelTypeInputExpr(['sidebar', 'var1'], '2.5');
    addSidebarPanel();
    panelTypeInputExpr(['sidebar', 'var2'], 'var1');
    dashboardConvertToControl(['sidebar', 'var2']);

    // Add table panel
    panelTypeInputExpr(['main', 'panel0'], 'var0');
    panelChangeId(['main', 'panel0'], 'table');
    tableAppendColumn(['main', 'panel0'], 'row ** var1');
    tableCheckContainsValue(['main', 'panel0'], '5.657');

    // Add another table panel
    addMainPanel();
    panelTypeInputExpr(['main', 'panel1'], 'panel0.all_rows');
    tableCheckContainsValue(['main', 'panel1'], '5.657');

    // Add plot panel
    addMainPanel();
    panelTypeInputExpr(['main', 'panel2'], 'panel0.all_rows');
    panelChangeId(['main', 'panel2'], 'plot');

    sliderSetValue(['sidebar', 'var2'], 0.5);
    tableCheckContainsValue(['main', 'panel0'], '1.414');
    tableCheckContainsValue(['main', 'panel1'], '1.414');
  });
});
