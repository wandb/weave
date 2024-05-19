import {goToHomePage} from '../testlib';

describe('board template notebook links', () => {
  it('check that board template notebook links to colab work', () => {
    goToHomePage();
    cy.contains('Board templates').click();

    cy.get('[data-testid="template-card"]').each(($el, index, $list) => {
      const currentEl = cy.get('[data-testid="template-card"]').eq(index);
      currentEl
        .trigger('mouseenter')
        .realHover()
        .trigger('mouseenter')
        .realHover()
        .contains('Try it out')
        .click();

      cy.get(
        'img[src="https://colab.research.google.com/assets/colab-badge.svg"]'
      )

        .parent('a')
        .each(($innerEl, index, $list) => {
          const href = $innerEl.prop('href');
          // check that the url starts with https://colab.research.google.com/github
          expect(href).to.match(
            /^https:\/\/colab\.research\.google\.com\/github/
          );

          const newHref = href
            .replace(
              'https://colab.research.google.com/github',
              'https://raw.githubusercontent.com'
            )
            .replace('blob/', '');

          // load the notebook.
          cy.request(newHref).then(response => {
            // check that the status code is 200
            expect(response.status).to.eq(200);
          });

          cy.origin(
            'https://colab.research.google.com',
            {args: {href}},
            ({href}) => {
              cy.visit(href);
              cy.contains('pip install').scrollIntoView().should('be.visible');
            }
          );
        });
      goToHomePage();
      cy.contains('Board templates').click();
    });
  });
});
