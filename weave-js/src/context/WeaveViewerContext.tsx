import {getCookie} from '@wandb/weave/common/util/cookie';
import getConfig from '@wandb/weave/config';
import React, {useCallback, useEffect, useRef, useState} from 'react';

type ViewerDataType = {
  authenticated: boolean;
  user_id?: string;
};

type WeaveViewerContextValue =
  | {loading: true}
  | {data: ViewerDataType; loading: false};

const WeaveViewerContext = React.createContext<
  WeaveViewerContextValue | undefined
>({
  loading: true,
});

export const useWeaveViewer = () => {
  const res = React.useContext(WeaveViewerContext);
  if (res === undefined) {
    throw new Error(
      'useWeaveViewer must be used within a WeaveViewerContextProvider'
    );
  }
  return res;
};

export const useIsAuthenticated = () => {
  const weaveViewer = useWeaveViewer();
  return weaveViewer.loading ? undefined : weaveViewer.data.authenticated;
};

export const WeaveViewerContextProvider: React.FC = ({children}) => {
  const viewerData = useWeaveViewerData();
  return (
    <WeaveViewerContext.Provider value={viewerData}>
      {children}
    </WeaveViewerContext.Provider>
  );
};

// TODO: currently deprecated, but works in all browsers
declare function btoa(s: string): string;

const useWeaveViewerData = (skip: boolean = false) => {
  const [viewerData, setViewerData] = useState<
    {loading: true} | {data: ViewerDataType; loading: false}
  >({
    loading: true,
  });
  const setNoViewerData = useCallback(() => {
    setViewerData({
      data: {
        authenticated: false,
      },
      loading: false,
    });
  }, []);

  const anonApiKey = getCookie('anon_api_key');

  const isMounted = useRef(true);

  useEffect(() => {
    if (skip) {
      setNoViewerData();
    }
    const additionalHeaders: Record<string, string> = {};
    if (anonApiKey != null && anonApiKey !== '') {
      additionalHeaders['x-wandb-anonymous-auth-id'] = btoa(anonApiKey);
    }
    // eslint-disable-next-line wandb/no-unprefixed-urls
    fetch(getConfig().backendWeaveViewerUrl(), {
      credentials: 'include',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...additionalHeaders,
      },
    })
      .then(res => {
        if (!isMounted.current) {
          return;
        }
        if (res.status !== 200) {
          setNoViewerData();
          return;
        } else {
          return res.json();
        }
      })
      .then(json => {
        if (!isMounted.current) {
          return;
        }
        setViewerData({
          data: {
            authenticated: !!(json?.authenticated ?? false),
            user_id: json?.user_id,
          },
          loading: false,
        });
      })
      .catch(err => {
        if (!isMounted.current) {
          return;
        }
        setNoViewerData();
      });

    return () => {
      isMounted.current = false;
    };
  }, [anonApiKey, setNoViewerData, skip]);
  return viewerData;
};
