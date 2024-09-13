import React from 'react'
import { useGridApiRef } from "@mui/x-data-grid-pro";
import { ObjectViewer } from "../../pages/CallPage/ObjectViewer";
import { useWFHooks } from "../../pages/wfReactInterface/context";
import { CustomWeaveTypePayload } from "../customWeaveType.types";
import { LoadingDots } from "@wandb/weave/components/LoadingDots";
import { TEAL_600 } from '@wandb/weave/common/css/color.styles';
import { Tailwind } from '@wandb/weave/components/Tailwind';

type JsonBlobPayload = CustomWeaveTypePayload<
    'weave.type_serializers.JSONBlob.jsonblob.JSONBlob',
    {'blob.json': string}
>;

export const JsonBlob: React.FC<{
    entity: string;
    project: string;
    data: JsonBlobPayload;
}> = props => {
    const {useFileContent} = useWFHooks();
    const objectBinary = useFileContent(
        props.entity,
        props.project,
        props.data.files['blob.json']
    );

    const [expanded, setExpanded] = React.useState(false);

    if (objectBinary.loading) {
        return <LoadingDots />;
    } else if (objectBinary.result == null) {
        return <span></span>;
    }

    // encode then parse
    const enc = new TextDecoder("utf-8");
    const object = JSON.parse(enc.decode(objectBinary.result));

    const objectPreview = Object.entries(object).slice(0, 10).join(",")
    const size = (objectBinary.result.byteLength / 1024 / 1024).toFixed(2);
    const handleToggle = () => {
        setExpanded(!expanded);
    };

    return (
        <Tailwind>
            {expanded ? (
                <div onClick={handleToggle}>
                    {objectPreview}
                </div>
            ):(
                <div onClick={handleToggle} className="cursor-pointer font-bold text-moon-700 hover:text-teal-500">
                {`JsonBlob (${size} MB)`}
            </div>
            )}
        </Tailwind>
    );
};
