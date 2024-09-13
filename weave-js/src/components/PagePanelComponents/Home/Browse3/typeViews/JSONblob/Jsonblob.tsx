import {Button} from '@wandb/weave/components/Button';
import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React from 'react';

import {initiateDownloadFromBlob} from '../../pages/CallsPage/CallsTableButtons';
import {useWFHooks} from '../../pages/wfReactInterface/context';
import {CustomWeaveTypePayload} from '../customWeaveType.types';

type JsonBlobPayload = CustomWeaveTypePayload<
  'weave.type_serializers.JSONBlob.jsonblob.JSONBlob',
  {'blob.json': string}
>;

export const JsonBlob: React.FC<{
  entity: string;
  project: string;
  data: JsonBlobPayload;
}> = props => {
  const [downloading, setDownloading] = React.useState(false);

  return (
    <Tailwind>
      {downloading ? (
        <JsonDownloader {...props} setDownloading={setDownloading} />
      ) : (
        <div
          onClick={() => setDownloading(true)}
          className="cursor-pointer font-bold text-moon-700 hover:text-teal-500">
          {`JsonBlob`}
        </div>
      )}
    </Tailwind>
  );
};

const JsonDownloader: React.FC<{
  entity: string;
  project: string;
  data: JsonBlobPayload;
  setDownloading: (downloading: boolean) => void;
}> = props => {
  const {useFileContent} = useWFHooks();
  const objectBinary = useFileContent(
    props.entity,
    props.project,
    props.data.files['blob.json']
  );

  if (objectBinary.loading) {
    return <LoadingDots />;
  } else if (objectBinary.result == null) {
    return <span></span>;
  }

  const arrayBuffer = objectBinary.result as any as ArrayBuffer;
  const blob = new Blob([arrayBuffer], {type: 'application/json'});
  const size = (objectBinary.result.byteLength / 1024 / 1024).toFixed(2);

  const download = () => {
    if (objectBinary.result) {
      initiateDownloadFromBlob(
        blob,
        `${props.entity}-${props.project}-blob.json`
      );
      props.setDownloading(false);
    }
  };
  return (
    <Button icon="download" size="small" onClick={download}>
      {`${size} MB`}
    </Button>
  );
};
