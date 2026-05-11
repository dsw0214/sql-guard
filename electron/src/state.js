export const state = {
    reviewing: false,
    lastResult: null,
    lastRenderMode: "hybrid",
    currentExpandedFile: null,
    previewMatchIndex: -1,
    previewMatchCount: 0,
    previewState: {
        type: null,
        filename: null,
        content: null,
        mimeType: null,
    },
    confirmResolver: null,
};
