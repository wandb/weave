/**
 * Legacy (global) stylesheets can sometimes have impacts outside of their intended
 * import area, which can cause styling regressions when code-splitting, due to
 * either missing or mis-ordered styles.
 *
 * To make sure stylesheets always load -- and always load in the right order --
 * move them into this file, which is always imported immediately at app load.
 */

import '@wandb/common/assets/careyfont/css/careyfont-embedded.css';
import '@wandb/common/components/elements/Toast.css';
import '@wandb/common/components/JupyterViewer.css';
import '@wandb/weave-ui/components/Panel2/PanelTable/baseTable.css';
import '@wandb/common/components/Tags/Tags.less';
import '@wandb/common/css/App.less';
import '@wandb/weave-ui/css/ControlBox.less';
import '@wandb/common/css/DragDrop.less';
import '@wandb/common/css/EditableField.less';
import '@wandb/common/css/Markdown.less';
import '@wandb/common/css/NumberInput.less';
import '@wandb/common/index.css';
import 'katex/dist/katex.css';
import 'react-base-table/styles.css';
import 'react-datetime/css/react-datetime.css';
import 'react-resizable/css/styles.css';
import 'react-table/react-table.css';
import 'react-toastify/dist/ReactToastify.min.css';
import '@wandb/semantic/semantic.min.css';
