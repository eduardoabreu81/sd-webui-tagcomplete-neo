const LORA_REGEX = /<(?!e:|h:|c:)[^,> ]*>?/g;
const LORA_TRIGGER = () => TAC_CFG.useLoras && tagword.match(LORA_REGEX);

class LoraParser extends BaseTagParser {
    parse() {
        // Show lora
        let tempResults = [];
        // Extract search term only from the part after the colon separator.
        // Typing "<lora" or "<l" (no colon yet) should show all results, not
        // filter for filenames containing "lora".
        const colonIdx = tagword.indexOf(":");
        const searchTerm = colonIdx >= 0 ? tagword.slice(colonIdx + 1) : "";
        if (searchTerm.length > 0) {
            let filterCondition = x => {
                let regex = new RegExp(escapeRegExp(searchTerm, true), 'i');
                return regex.test(x.toLowerCase()) || regex.test(x.toLowerCase().replaceAll(" ", "_"));
            };
            tempResults = loras.filter(x => filterCondition(x[0])); // Filter by tagword
        } else {
            tempResults = loras;
        }

        // Add final results
        let finalResults = [];
        tempResults.forEach(t => {
            const text = t[0].trim();
            let lastDot = text.lastIndexOf(".") > -1 ? text.lastIndexOf(".") : text.length;
            let lastSlash = text.lastIndexOf("/") > -1 ? text.lastIndexOf("/") : -1;
            let name = text.substring(lastSlash + 1, lastDot);

            let result = new AutocompleteResult(name, ResultType.lora)
            result.meta = "Lora";
            result.sortKey = t[1];
            result.hash = t[2];
            finalResults.push(result);
        });

        return finalResults;
    }
}

// Maps stem (display name) -> alias from Forge Neo safetensors metadata.
// Alias is what Forge Neo actually uses to reference a LoRA at runtime.
const loraAliasMap = {};

async function load() {
    if (loras.length === 0) {
        try {
            const rows = (await loadCSV(`${tagBasePath}/temp/lora.txt`))
                .filter(x => x[0]?.trim().length > 0); // Remove empty lines
            loras = rows.map(x => [x[0]?.trim(), x[1], x[2]]);
            // Build stem -> alias lookup from column 4
            for (const x of rows) {
                const path = x[0]?.trim();
                const alias = x[3]?.trim();
                if (path && alias) {
                    const lastDot = path.lastIndexOf(".") > -1 ? path.lastIndexOf(".") : path.length;
                    const lastSlash = path.lastIndexOf("/") > -1 ? path.lastIndexOf("/") : -1;
                    const stem = path.substring(lastSlash + 1, lastDot);
                    loraAliasMap[stem] = alias;
                }
            }
        } catch (e) {
            console.error("Error loading lora.txt: " + e);
        }
    }
}

async function sanitize(tagType, text) {
    if (tagType === ResultType.lora) {
        let multiplier = TAC_CFG.extraNetworksDefaultMultiplier;
        let info = await fetchTacAPI(`tacapi/v1/lora-info/${text}`)
        if (info && info["preferred weight"]) {
            multiplier = info["preferred weight"];
        }
        // Use Forge Neo alias if available; fallback to stem (display name)
        const insertName = loraAliasMap[text] ?? text;
        return `<lora:${insertName}:${multiplier}>`;
    }
    return null;
}

PARSERS.push(new LoraParser(LORA_TRIGGER));

// Add our utility functions to their respective queues
QUEUE_FILE_LOAD.push(load);
QUEUE_SANITIZE.push(sanitize);
