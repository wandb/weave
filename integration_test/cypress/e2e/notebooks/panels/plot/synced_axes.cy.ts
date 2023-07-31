import {checkWeaveNotebookOutputs} from '../../notebooks';

describe('../examples/panels/plot/synced_axes.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/panels/plot/synced_axes.ipynb')
    );
});