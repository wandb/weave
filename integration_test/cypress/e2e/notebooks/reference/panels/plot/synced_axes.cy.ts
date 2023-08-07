import {checkWeaveNotebookOutputs} from '../../../notebooks';

describe('../examples/reference/panels/plot/synced_axes.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/reference/panels/plot/synced_axes.ipynb')
    );
});