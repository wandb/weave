const stringIsLikelyURL = (str: string) => {
    return str.startsWith('http://') || str.startsWith('https://');
}

export const stringIsLikelyImageURL = (str: string) => {
    return (
        // OpenAI DALL-E API image URLs
        str.startsWith('https://oaidalleapiprodscus.blob.core.windows.net') || 
        // Other image URLs
        (stringIsLikelyURL(str) && str.match(/\.(jpeg|jpg|gif|png)$/) !== null)
    );
}
