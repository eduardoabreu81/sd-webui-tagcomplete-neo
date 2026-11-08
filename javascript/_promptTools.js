// Prompt text helpers for the used-tag selection and the prompt formatter.
// Pure functions without DOM access. Ideas adapted from
// newtextdoc1111/ComfyUI-Autocomplete-Plus (MIT).
var TacPromptTools = (() => {
    // Angle brackets are left out on purpose: emoticon tags such as ">_<" or ":<" would otherwise
    // read as unbalanced, and extra networks like <lora:name:1> contain no commas anyway.
    const PAIRS = { "(": ")", "[": "]", "{": "}" };
    const CLOSING = new Set(Object.values(PAIRS));
    const LINE_KEYWORDS = /^(BREAK|AND|ADDCOMM|ADDBASE|ADDCOL|ADDROW)$/;

    // Splits text at top-level commas and newlines. Separators inside brackets and quotes are kept,
    // and escaped characters are skipped. `balanced` is false when a bracket or quote never closes
    // or a closing bracket has no opener.
    function splitSegments(text) {
        const segments = [];
        const stack = [];
        let start = 0, quote = false, escape = false, stray = false;
        for (let i = 0; i < text.length; i++) {
            const c = text[i];
            if (escape) { escape = false; continue; }
            if (c === "\\") { escape = true; continue; }
            if (c === '"') { quote = !quote; continue; }
            if (quote) continue;
            if (PAIRS[c]) {
                stack.push(PAIRS[c]);
            } else if (stack.length && c === stack[stack.length - 1]) {
                stack.pop();
            } else if (CLOSING.has(c)) {
                stray = true;
            } else if (!stack.length && (c === "," || c === "\n")) {
                segments.push({ start, end: i, text: text.slice(start, i), separator: c });
                start = i + 1;
            }
        }
        segments.push({ start, end: text.length, text: text.slice(start), separator: "" });
        return { segments, balanced: !stack.length && !quote && !stray };
    }

    // Like splitSegments, but falls back to plain comma/newline splitting for unbalanced text
    // (e.g. a ":(" emoticon), so tag lookups still work there.
    function tagSegments(text) {
        const parsed = splitSegments(text);
        if (parsed.balanced) return parsed.segments;
        const segments = [];
        let start = 0;
        for (let i = 0; i <= text.length; i++) {
            if (i === text.length || text[i] === "," || text[i] === "\n") {
                segments.push({ start, end: i, text: text.slice(start, i), separator: text[i] || "" });
                start = i + 1;
            }
        }
        return segments;
    }

    // Reduces a prompt segment to a comparable tag name: drops emphasis brackets and weights,
    // unescapes parentheses, removes the ANIMA '@' artist prefix and treats spaces as underscores.
    function normalizeTag(text) {
        let tag = String(text ?? "").trim();
        for (;;) {
            const match = tag.match(/^\((.*?)(?::\s*-?\d+(?:\.\d+)?)?\)$/s)
                || tag.match(/^\[(.*)\]$/s)
                || tag.match(/^\{(.*)\}$/s);
            if (!match) break;
            tag = match[1].trim();
        }
        return tag
            .replace(/\\([()[\]{}])/g, "$1")
            .replace(/^@/, "")
            .replace(/\s+/g, "_")
            .toLowerCase();
    }

    // The segment containing the caret, or null.
    function segmentAt(text, pos) {
        return tagSegments(text).find(s => s.start <= pos && pos <= s.end) || null;
    }

    // First occurrence of `tag` as its own segment, outside the segment that contains `ignorePos`.
    // Returns the trimmed range of the occurrence.
    function findTag(text, tag, ignorePos = -1) {
        const key = normalizeTag(tag);
        if (!key) return null;
        for (const s of tagSegments(text)) {
            if (s.start <= ignorePos && ignorePos <= s.end) continue;
            if (normalizeTag(s.text) !== key) continue;
            const lead = s.text.length - s.text.trimStart().length;
            return { start: s.start + lead, end: s.start + s.text.trimEnd().length };
        }
        return null;
    }

    // Range that removes a segment together with one adjacent comma, so removing "b" from
    // "a, b, c" leaves "a, c". Newlines are never removed, to keep the line layout.
    function removalRange(text, segment) {
        if (segment.start > 0 && text[segment.start - 1] === ",") {
            return { start: segment.start - 1, end: segment.end };
        }
        if (segment.separator === ",") {
            let end = segment.end + 1;
            while (end < text.length && (text[end] === " " || text[end] === "\t")) end++;
            return { start: segment.start, end };
        }
        return { start: segment.start, end: segment.end };
    }

    // Multi-word queries for the plain words right before the caret, so "long hai" can complete to
    // long_hair: the last `maxWords` down to 2 words joined with "_", longest first. Only the text
    // after the last comma, newline or "|" counts, and it must be plain words separated by single
    // spaces; prompt syntax, wildcards or a trailing space return nothing.
    function spacedTagQueries(textBeforeCaret, maxWords = 3) {
        const field = String(textBeforeCaret ?? "").match(/[^,\n|]*$/)[0].trimStart();
        if (!field || /\s$/.test(field) || /\s\s|\t/.test(field)) return [];
        if (/[<>()[\]{}:*@$"\\]|__/.test(field)) return [];
        const words = field.split(" ");
        const queries = [];
        for (let n = Math.min(maxWords, words.length); n >= 2; n--) {
            queries.push(words.slice(-n).join("_").toLowerCase());
        }
        return queries;
    }

    // Number lists and single-letter templates (e.g. LoRA block weights "1,0,0,A") are data, not tags.
    function looksLikeData(segments) {
        const parts = segments.map(s => s.text.trim()).filter(Boolean);
        return parts.length > 0 && parts.every(p => /^[A-Za-z]$/.test(p) || /^-?\d+(\.\d+)?$/.test(p));
    }

    // Tidies a prompt: trims it, drops empty tags and joins the tags of each line with `separator`.
    // Each line with tags then ends with `lineEnd` ("," with `trailingComma`), and the last line
    // with `lastLineEnd` (default `lineEnd`); BREAK/AND keyword lines end with nothing.
    // Line breaks, bracket contents and quoted text are kept as written.
    // Text with unbalanced brackets or quotes is returned unchanged.
    function formatPrompt(text, { separator = ", ", trailingComma = false, lineEnd, lastLineEnd } = {}) {
        if (text == null) return text;
        if (!text.trim()) return "";
        const { segments, balanced } = splitSegments(text.trim());
        if (!balanced || looksLikeData(segments)) return text;
        lineEnd ??= trailingComma ? "," : "";
        lastLineEnd ??= lineEnd;

        const lines = [];
        let tags = [];
        for (const s of segments) {
            const tag = s.text.trim();
            if (tag) tags.push(tag);
            if (s.separator === ",") continue;
            let line = tags.join(separator);
            if (line && !LINE_KEYWORDS.test(line)) line += s.separator ? lineEnd : lastLineEnd;
            lines.push(line);
            tags = [];
        }
        return lines.join("\n");
    }

    return { splitSegments, tagSegments, normalizeTag, segmentAt, findTag, removalRange, spacedTagQueries, formatPrompt };
})();
