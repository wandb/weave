
import React from "react";

import { WandbCore } from "../core.js";

const WandbContext = React.createContext<WandbCore | null>(null);

export function WandbProvider(props: { client: WandbCore, children: React.ReactNode }): React.ReactNode { 
  return (
    <WandbContext.Provider value={props.client}>
      {props.children}
    </WandbContext.Provider>
  );
}

export function useWandbContext(): WandbCore { 
  const value = React.useContext(WandbContext);
  if (value === null) {
    throw new Error("SDK not initialized. Create an instance of WandbCore and pass it to <WandbProvider />.");
  }
  return value;
}
