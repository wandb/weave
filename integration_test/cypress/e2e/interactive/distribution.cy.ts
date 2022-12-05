import {exec} from '../testlib';

describe('distribution interactions', () => {
  it('can configure a python panel from scratch by clicking', () => {
    exec('python cypress/e2e/interactive/distribution.py', 10000).then(
      result => {
        const url = result.stdout;
        cy.visit(url);
        cy.wait(1000);

        cy.get('i.cog').click();
        cy.wait(1000);

        // modify the expression to select some data
        const valueEe = cy
          .get('[data-test=weave-sidebar]')
          .find('[data-test=expression-editor-container]')
          .eq(1)
          .find('[data-slate-editor=true]')
          .click({force: true})
          .type('["loss1"]', {force: true})
          .type('{enter}', {force: true});

        // Click ok in the sidebar
        cy.get('[data-test=ok-panel-config]').click();

        cy.get('rect').should('have.length.gte', 2);
      }
    );
  });
});
