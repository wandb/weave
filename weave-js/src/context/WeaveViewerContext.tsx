import {getCookie} from '@wandb/weave/common/util/cookie';
import getConfig from '@wandb/weave/config';
import React, {useCallback, useEffect, useRef, useState} from 'react';

type ViewerDataType = {
  authenticated: boolean;
  signupRequired: boolean;
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

export const useIsSignupRequired = () => {
  const weaveViewer = useWeaveViewer();
  return weaveViewer.loading ? undefined : weaveViewer.data.signupRequired;
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
  const setNoViewerData = useCallback((signupRequired: boolean) => {
    setViewerData({
      data: {
        authenticated: false,
        signupRequired,
      },
      loading: false,
    });
  }, []);

  const anonApiKey = getCookie('anon_api_key');

  const isMounted = useRef(true);

  useEffect(() => {
    if (skip) {
      setNoViewerData(false);
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
        if (res.status === 200) {
          return res.json();
        }
        if (res.status === 403) {
          return res.text();
        }
        setNoViewerData(false);
        return;
      })
      .then(body => {
        if (!isMounted.current) {
          return;
        }
        if (typeof body === 'string') {
          // This was a 403.
          const signupRequired = body === 'Signup required';
          setNoViewerData(signupRequired);
          return;
        }
        const json = body;
        setViewerData({
          data: {
            authenticated: !!(json?.authenticated ?? false),
            signupRequired: false,
            user_id: json?.user_id,
          },
          loading: false,
        });
      })
      .catch(err => {
        if (!isMounted.current) {
          return;
        }
        setNoViewerData(false);
      });

    return () => {
      isMounted.current = false;
    };
  }, [anonApiKey, setNoViewerData, skip]);
  return viewerData;
};
