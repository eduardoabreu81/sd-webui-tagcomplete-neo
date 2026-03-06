const LORA_REGEX = /<(?!e:|h:|c:)[^,> ]*>?/g;
const LORA_TRIGGER = () => TAC_CFG.useLoras && tagword.match(LORA_REGEX);

class LoraParser extends BaseTagParser {
    parse() {
        // Show lora
        let tempResults = [];
        if (tagword !== "<" && tagword !== "<l:" && tagword !== "<lora:") {
            let searchTerm = tagword.replace("<lora:", "").replace("<l:", "").replace("<", "");
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
            // t[3] is the alias computed by the Python backend (respects Forge Neo's
            // "lora_preferred_name" setting). Falls back to the filename stem if absent.
            result.aliases = (t[3] && t[3].trim()) ? [t[3].trim()] : null;
            finalResults.push(result);
        });

        return finalResults;
    }
}

async function load() {
    if (loras.length === 0) {
        try {
            loras = (await loadCSV(`${tagBasePath}/temp/lora.txt`))
                .filter(x => x[0]?.trim().length > 0) // Remove empty lines
                .map(x => [x[0]?.trim(), x[1], x[2], x[3]?.trim()]); // name, sortKey, hash, alias
        } catch (e) {
            console.error("Error loading lora.txt: " + e);
        }
    }
}

async function sanitize(tagType, text) {
    if (tagType === ResultType.lora) {
        let multiplier = TAC_CFG.extraNetworksDefaultMultiplier;

        // Find the lora entry that matches the display name (filename stem) so we
        // can retrieve the alias column. The alias is what Forge Neo expects inside
        // <lora:ALIAS:weight> — it already respects the user's "lora_preferred_name"
        // setting ("Alias from file" = ss_output_name, "Filename" = filename stem).
        const loraEntry = loras.find(x => {
            const t = x[0] ? x[0].trim() : "";
            const lastDot = t.lastIndexOf(".") > -1 ? t.lastIndexOf(".") : t.length;
            const lastSlash = t.lastIndexOf("/") > -1 ? t.lastIndexOf("/") : -1;
            return t.substring(lastSlash + 1, lastDot) === text;
        });
        // insertName is the token that goes into the prompt; text is the display name
        // used to locate the .json sidecar (always named after the filename stem).
        const insertName = (loraEntry && loraEntry[3]) ? loraEntry[3] : text;

        let info = await fetchTacAPI(`tacapi/v1/lora-info/${text}`);
        if (info && info["preferred weight"]) {
            multiplier = info["preferred weight"];
        }

        return `<lora:${insertName}:${multiplier}>`;
    }
    return null;
}

PARSERS.push(new LoraParser(LORA_TRIGGER));

// Add our utility functions to their respective queues
QUEUE_FILE_LOAD.push(load);
QUEUE_SANITIZE.push(sanitize);
