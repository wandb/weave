describe('empty spec', () => {
  it('passes', () => {
    // If the notebook output is not clear, this will take too long.
    // TODO: auto-clear
    cy.visit('http://localhost:8888/notebooks/examples/vis/Distribution.ipynb?token=abcd')

    // Restart and run all
    cy.get('#kernellink').click()
    cy.get('#restart_run_all a').click()
    cy.get('button.btn-danger').click()
    cy.wait(2000)

    // Wait til all cells are done running and 
    cy.get('.cell.running', {timeout: 30000}).should('not.exist', )
    cy.get('.output_area .output_error', {timeout: 1000}).should('not.exist', )

    cy.get('#site').scrollTo('bottom', {duration: 2000})
    cy.get('iframe', {timeout: 30000})
      .each(el => cy.wrap(el)
        .its('0.contentDocument', {timeout: 30000})
        .should('exist')
        .its('body')
        .should('not.be.undefined')
        .then(cy.wrap)
        .find('.plotly', {timeout: 30000})
        .should('have.length', 1))
  })
})