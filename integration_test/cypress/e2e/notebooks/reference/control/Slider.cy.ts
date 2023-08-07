import {checkWeaveNotebookOutputs} from '../../notebooks';

describe('../examples/reference/control/Slider.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/reference/control/Slider.ipynb')
    );
});