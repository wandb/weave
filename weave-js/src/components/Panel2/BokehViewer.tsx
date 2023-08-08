import * as React from 'react';
import {Card} from 'semantic-ui-react';

interface BokehViewerProps {
  headerElements?: JSX.Element[];
  notFoundElements?: JSX.Element[];
  contentNotFound?: boolean;
  bokehJson?: any;
}

// This injects a bokeh library fetch based on the version of the bokeh content. a bit hacky,
// but I think the only way to ensure compatibility with the user's python bokeh version and the
// JS version.
const loadBokehLibrary = (
  version: string = '2.2.3',
  callback: () => void = () => {}
) => {
  const scriptID = '__bokeh_lib_injection__';
  const existingScript = document.getElementById(scriptID);
  if (!existingScript) {
    const script = document.createElement('script');
    script.src = `https://cdn.bokeh.org/bokeh/release/bokeh-${version}.min.js`;
    script.id = scriptID;
    document.body.appendChild(script);
    script.addEventListener('load', callback);
  } else if (!(window as any).Bokeh) {
    existingScript.addEventListener('load', callback);
  } else {
    callback();
  }
};

const BokehViewer = (props: BokehViewerProps) => {
  const [libraryLoaded, setLibraryLoaded] = React.useState<boolean>(false);
  if (!props.bokehJson?.version) {
    return <>-</>;
  } else if (!libraryLoaded) {
    loadBokehLibrary(props.bokehJson.version, () => {
      setLibraryLoaded(true);
    });
    return <></>;
  } else {
    // See https://github.com/bokeh/bokeh/blob/55a0a5d33376abb029506e7c1facc85a2b2a2fa7/bokehjs/src/lib/core/logging.ts#L12
    (window as any).Bokeh.logger.set_level('error');
    return <BokehViewerInner {...props} />;
  }
};

const BokehViewerInner = (props: BokehViewerProps) => {
  const bokehDivRef = React.useRef<HTMLDivElement>(null);
  const bokehDivId = React.useMemo(() => '_bokeh__' + new Date().getTime(), []);

  React.useEffect(() => {
    if (!!props.bokehJson) {
      if (bokehDivRef.current) {
        bokehDivRef.current.innerHTML = '';
      }
      // Simple Bokeh objects will not have multiple roots. So
      // we can just use the first root_id. This was discovered
      // by unit tests creating simple Bokeh objects.
      let rootId = 0;
      if (props.bokehJson.roots.root_ids != null) {
        rootId = props.bokehJson.roots.root_ids[0];
      }
      (window as any).Bokeh.embed.embed_item({
        doc: props.bokehJson,
        root_id: rootId,
        target_id: bokehDivId,
      });
    }
  }, [props.bokehJson, bokehDivId]);

  return (
    <div style={{padding: '10px', height: '100%', width: '100%'}}>
      <Card className="bokeh-card" style={{width: '100%'}}>
        {props.headerElements}

        {!!props.contentNotFound || !props.bokehJson ? (
          !!props.notFoundElements ? (
            props.notFoundElements
          ) : null
        ) : (
          <div ref={bokehDivRef} id={bokehDivId}></div>
        )}
      </Card>
    </div>
  );
};

export default BokehViewer;
