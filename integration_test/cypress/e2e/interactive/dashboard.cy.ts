import promisify from 'cypress-promise';
import {exec} from '../testlib';

const gotoBlankDashboard = async () => {
  await promisify(exec('python cypress/e2e/interactive/blank.py', 10000));
  // const url = result.stdout;
  // E.g. for devmode
  const url =
    '/?fullScreen&expNode=%7B%22nodeType%22%3A%20%22output%22%2C%20%22type%22%3A%20%22none%22%2C%20%22fromOp%22%3A%20%7B%22name%22%3A%20%22get%22%2C%20%22inputs%22%3A%20%7B%22uri%22%3A%20%7B%22nodeType%22%3A%20%22const%22%2C%20%22type%22%3A%20%22string%22%2C%20%22val%22%3A%20%22local-artifact%3A///dashboard-Group%3Alatest/obj%22%7D%7D%7D%7D';
  // '/?fullScreen=&expNode=%7B%22nodeType%22%3A+%22output%22%2C+%22type%22%3A+%7B%22type%22%3A+%22Group%22%2C+%22_base_type%22%3A+%7B%22type%22%3A+%22Panel%22%2C+%22_base_type%22%3A+%7B%22type%22%3A+%22Object%22%7D%7D%2C+%22_is_object%22%3A+true%2C+%22input_node%22%3A+%7B%22type%22%3A+%22function%22%2C+%22inputTypes%22%3A+%7B%7D%2C+%22outputType%22%3A+%22invalid%22%7D%2C+%22vars%22%3A+%7B%22type%22%3A+%22typedDict%22%2C+%22propertyTypes%22%3A+%7B%7D%7D%2C+%22config%22%3A+%7B%22type%22%3A+%22GroupConfig%22%2C+%22_base_type%22%3A+%7B%22type%22%3A+%22Object%22%7D%2C+%22_is_object%22%3A+true%2C+%22items%22%3A+%7B%22type%22%3A+%22typedDict%22%2C+%22propertyTypes%22%3A+%7B%22op-multi_distribution0%22%3A+%7B%22type%22%3A+%22op-multi_distribution%22%2C+%22_base_type%22%3A+%7B%22type%22%3A+%22Panel%22%2C+%22_base_type%22%3A+%7B%22type%22%3A+%22Object%22%7D%7D%2C+%22_is_object%22%3A+true%2C+%22input_node%22%3A+%7B%22type%22%3A+%22function%22%2C+%22inputTypes%22%3A+%7B%7D%2C+%22outputType%22%3A+%7B%22type%22%3A+%22list%22%2C+%22objectType%22%3A+%7B%22type%22%3A+%22typedDict%22%2C+%22propertyTypes%22%3A+%7B%22name%22%3A+%22string%22%2C+%22loss1%22%3A+%7B%22type%22%3A+%22list%22%2C+%22objectType%22%3A+%22float%22%7D%2C+%22loss2%22%3A+%7B%22type%22%3A+%22list%22%2C+%22objectType%22%3A+%22float%22%7D%2C+%22str_val%22%3A+%7B%22type%22%3A+%22list%22%2C+%22objectType%22%3A+%22string%22%7D%7D%7D%7D%7D%2C+%22vars%22%3A+%7B%22type%22%3A+%22typedDict%22%2C+%22propertyTypes%22%3A+%7B%7D%7D%2C+%22config%22%3A+%7B%22type%22%3A+%22op-multi_distributionConfig%22%2C+%22_base_type%22%3A+%7B%22type%22%3A+%22Object%22%7D%2C+%22_is_object%22%3A+true%2C+%22value_fn%22%3A+%7B%22type%22%3A+%22function%22%2C+%22inputTypes%22%3A+%7B%22item%22%3A+%7B%22type%22%3A+%22typedDict%22%2C+%22propertyTypes%22%3A+%7B%22name%22%3A+%22string%22%2C+%22loss1%22%3A+%22float%22%2C+%22loss2%22%3A+%22float%22%2C+%22str_val%22%3A+%22string%22%7D%7D%7D%2C+%22outputType%22%3A+%7B%22type%22%3A+%22typedDict%22%2C+%22propertyTypes%22%3A+%7B%22name%22%3A+%22string%22%2C+%22loss1%22%3A+%22float%22%2C+%22loss2%22%3A+%22float%22%2C+%22str_val%22%3A+%22string%22%7D%7D%7D%2C+%22label_fn%22%3A+%7B%22type%22%3A+%22function%22%2C+%22inputTypes%22%3A+%7B%22item%22%3A+%7B%22type%22%3A+%22typedDict%22%2C+%22propertyTypes%22%3A+%7B%22name%22%3A+%22string%22%2C+%22loss1%22%3A+%22float%22%2C+%22loss2%22%3A+%22float%22%2C+%22str_val%22%3A+%22string%22%7D%7D%7D%2C+%22outputType%22%3A+%22invalid%22%7D%2C+%22bin_size%22%3A+%7B%22type%22%3A+%22function%22%2C+%22inputTypes%22%3A+%7B%7D%2C+%22outputType%22%3A+%22float%22%7D%7D%2C+%22id%22%3A+%22string%22%7D%7D%7D%2C+%22gridConfig%22%3A+%22none%22%2C+%22liftChildVars%22%3A+%22none%22%2C+%22allowedPanels%22%3A+%22none%22%2C+%22enableAddPanel%22%3A+%22none%22%2C+%22childNameBase%22%3A+%22none%22%2C+%22showExpressions%22%3A+%22boolean%22%2C+%22layered%22%3A+%22boolean%22%2C+%22preferHorizontal%22%3A+%22boolean%22%2C+%22equalSize%22%3A+%22boolean%22%2C+%22style%22%3A+%22string%22%2C+%22grid%22%3A+%22boolean%22%7D%2C+%22id%22%3A+%22string%22%7D%2C+%22fromOp%22%3A+%7B%22name%22%3A+%22get%22%2C+%22inputs%22%3A+%7B%22uri%22%3A+%7B%22nodeType%22%3A+%22const%22%2C+%22type%22%3A+%22string%22%2C+%22val%22%3A+%22local-artifact%3A%2F%2F%2Fdashboard-op-multi_distribution0%3Alatest%2Fobj%22%7D%7D%7D%7D&exp=get%28%0A++++%22local-artifact%3A%2F%2F%2Fdashboard-op-multi_distribution0%3Alatest%2Fobj%22%29';
  cy.viewport(1600, 900);
  cy.visit(url);
  cy.wait(2000);
  cy.get('[data-cy="new-dashboard-input"]').click().type('test{enter}');
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
