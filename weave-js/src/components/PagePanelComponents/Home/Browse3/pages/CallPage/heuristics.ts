export const stringIsLikelyImageURL = (str: string) => {
    return (
        // OpenAI DALL-E API image URLs
        str.startsWith('https://oaidalleapiprodscus.blob.core.windows.net') || 
        // Other image URLs
        (str.startsWith('https://') && str.match(/\.(jpeg|jpg|gif|png)$/) !== null)
    );
}
