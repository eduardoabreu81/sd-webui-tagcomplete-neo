const LYCO_REGEX = /<(?!e:|h:|c:)[^,> ]*>?/g;
const LYCO_TRIGGER = () => TAC_CFG.useLycos && tagword.match(LYCO_REGEX);

class LycoParser extends BaseTagParser {
    parse() {
        // Show lyco
        let tempResults = [];
        if (tagword !== "<" && tagword !== "<l:" && tagword !== "<lyco:" && tagword !== "<lora:") {
            let searchTerm = tagword.replace("<lyco:", "").replace("<lora:", "").replace("<l:", "").replace("<", "");
            let filterCondition = x => {
                let regex = new RegExp(escapeRegExp(searchTerm, true), 'i');
                return regex.test(x.toLowerCase()) || regex.test(x.toLowerCase().replaceAll(" ", "_"));
            };
            tempResults = lycos.filter(x => filterCondition(x[0])); // Filter by tagword
        } else {
            tempResults = lycos;
        }

        // Add final results
        let finalResults = [];
        tempResults.forEach(t => {
            const text = t[0].trim();
            let lastDot = text.lastIndexOf(".") > -1 ? text.lastIndexOf(".") : text.length;
            let lastSlash = text.lastIndexOf("/") > -1 ? text.lastIndexOf("/") : -1;
            let name = text.substring(lastSlash + 1, lastDot);

            let result = new AutocompleteResult(name, ResultType.lyco)
            result.meta = "Lyco";
            result.sortKey = t[1];
            result.hash = t[2];
            result.aliases = (t[3] && t[3].trim()) ? [t[3].trim()] : null;
            finalResults.push(result);
        });

        return finalResults;
    }
}

async function load() {
    if (lycos.length === 0) {
        try {
            lycos = (await loadCSV(`${tagBasePath}/temp/lyco.txt`))
                .filter(x => x[0]?.trim().length > 0) // Remove empty lines
                .map(x => [x[0]?.trim(), x[1], x[2], x[3]?.trim()]); // name, sortKey, hash, alias
        } catch (e) {
            console.error("Error loading lyco.txt: " + e);
        }
    }
}

async function sanitize(tagType, text) {
    if (tagType === ResultType.lyco) {
        let multiplier = TAC_CFG.extraNetworksDefaultMultiplier;

        const lycoEntry = lycos.find(x => {
            const t = x[0] ? x[0].trim() : "";
            const lastDot = t.lastIndexOf(".") > -1 ? t.lastIndexOf(".") : t.length;
            const lastSlash = t.lastIndexOf("/") > -1 ? t.lastIndexOf("/") : -1;
            return t.substring(lastSlash + 1, lastDot) === text;
        });
        const insertName = (lycoEntry && lycoEntry[3]) ? lycoEntry[3] : text;

        let info = await fetchTacAPI(`tacapi/v1/lyco-info/${text}`);
        if (info && info["preferred weight"]) {
            multiplier = info["preferred weight"];
        }

        let prefix = TAC_CFG.useLoraPrefixForLycos ? "lora" : "lyco";
        return `<${prefix}:${insertName}:${multiplier}>`;
    }
    return null;
}

PARSERS.push(new LycoParser(LYCO_TRIGGER));

// Add our utility functions to their respective queues
QUEUE_FILE_LOAD.push(load);
QUEUE_SANITIZE.push(sanitize);
