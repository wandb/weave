import {exec, checkAllPanelsRendered} from '../testlib';

describe.skip('scatter interactions', () => {
  it('can select a region on a scatter plot and update another panel based on selection', () => {
    exec('python cypress/e2e/interactive/scatter.py', 10000).then(result => {
      const url = result.stdout;
      cy.visit(url);
      cy.wait(3000);

      checkAllPanelsRendered();

      // This does a plotly select
      cy.get('[data-test-weave-id=PanelPlotly] .svg-container .drag')
        .first()
        .trigger('mousedown', 200, 200, {force: true})
        .trigger('mousemove', 500, 500, {force: true})
        .trigger('mouseup', {force: true});

      checkAllPanelsRendered();

      // This scrolls the content area to the bottom. Unfortunate to need
      // >div>div
      cy.get('[data-test=panel-expression-content]>div>div').scrollTo('bottom');

      // The table shows the selected items, there should be some numbers
      // inside now.
      cy.get('.BaseTable__row-cell [data-test-weave-id=number]').should(
        'have.length.gte',
        10
      );
    });
  });
});
