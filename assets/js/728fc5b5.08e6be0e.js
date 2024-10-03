"use strict";(self.webpackChunkdocs=self.webpackChunkdocs||[]).push([[2873],{62586:(e,o,n)=>{n.r(o),n.d(o,{assets:()=>r,contentTitle:()=>s,default:()=>p,frontMatter:()=>i,metadata:()=>l,toc:()=>c});var t=n(85893),d=n(11151);const i={},s="Deploy",l={id:"guides/tools/deploy",title:"Deploy",description:"Deploy to GCP",source:"@site/docs/guides/tools/deploy.md",sourceDirName:"guides/tools",slug:"/guides/tools/deploy",permalink:"/guides/tools/deploy",draft:!1,unlisted:!1,editUrl:"https://github.com/wandb/weave/blob/master/docs/docs/guides/tools/deploy.md",tags:[],version:"current",lastUpdatedAt:1727953082e3,frontMatter:{},sidebar:"documentationSidebar",previous:{title:"Serve",permalink:"/guides/tools/serve"},next:{title:"Integrations",permalink:"/guides/integrations/"}},r={},c=[{value:"Deploy to GCP",id:"deploy-to-gcp",level:2}];function a(e){const o={admonition:"admonition",code:"code",h1:"h1",h2:"h2",p:"p",pre:"pre",...(0,d.a)(),...e.components};return(0,t.jsxs)(t.Fragment,{children:[(0,t.jsx)(o.h1,{id:"deploy",children:"Deploy"}),"\n",(0,t.jsx)(o.h2,{id:"deploy-to-gcp",children:"Deploy to GCP"}),"\n",(0,t.jsx)(o.admonition,{type:"note",children:(0,t.jsxs)(o.p,{children:[(0,t.jsx)(o.code,{children:"weave deploy"})," requires your machine to have ",(0,t.jsx)(o.code,{children:"gcloud"})," installed and configured. ",(0,t.jsx)(o.code,{children:"weave deploy gcp"})," will use pre-configured configuration when not directly specified by command line arguments."]})}),"\n",(0,t.jsx)(o.p,{children:"Given a Weave ref to any Weave Model you can run:"}),"\n",(0,t.jsx)(o.pre,{children:(0,t.jsx)(o.code,{children:"weave deploy gcp <ref>\n"})}),"\n",(0,t.jsxs)(o.p,{children:["to deploy a gcp cloud function that serves your model. The last line of the deployment will look like ",(0,t.jsx)(o.code,{children:"Service URL: <PATH_TO_MODEL>"}),". Visit ",(0,t.jsx)(o.code,{children:"<PATH_TO_MODEL>/docs"})," to interact with your model!"]}),"\n",(0,t.jsx)(o.p,{children:"Run"}),"\n",(0,t.jsx)(o.pre,{children:(0,t.jsx)(o.code,{children:"weave deploy gcp --help\n"})}),"\n",(0,t.jsx)(o.p,{children:"to see all command line options."})]})}function p(e={}){const{wrapper:o}={...(0,d.a)(),...e.components};return o?(0,t.jsx)(o,{...e,children:(0,t.jsx)(a,{...e})}):a(e)}},11151:(e,o,n)=>{n.d(o,{Z:()=>l,a:()=>s});var t=n(67294);const d={},i=t.createContext(d);function s(e){const o=t.useContext(i);return t.useMemo((function(){return"function"==typeof e?e(o):{...o,...e}}),[o,e])}function l(e){let o;return o=e.disableParentContext?"function"==typeof e.components?e.components(d):e.components||d:s(e.components),t.createElement(i.Provider,{value:o},e.children)}}}]);