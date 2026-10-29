const LORA_REGEX = /<(?!e:|h:|c:)[^,> ]*>?/g;
const LORA_TRIGGER = () => TAC_CFG.useLoras && tagword.match(LORA_REGEX);

// Architecture labels scripts/lora_arch.py can assign (lora_arch.LABELS); keep the two in step.
// A UI preset outside this list turns the architecture filter off instead of hiding every LoRA.
const LORA_ARCH_LABELS = new Set([
    "sd", "xl", "flux", "klein", "qwen", "qwen21", "lumina", "zit", "wan", "anima", "ernie", "pid",
    "krea", "moss", "fibo2", "flux3", "h3", "ideogram4", "yue2",
]);
const LORA_ARCH_SEPARATOR = " " + String.fromCharCode(0xb7) + " ";

// Forge Neo's UI preset, when the architecture filter can use it; null turns the filter off.
function currentLoraArchPreset() {
    if (!TAC_CFG.loraArchFilter || TAC_CFG.loraArchFilter === "Off") return null;
    const value = gradioApp().querySelector("#forge_ui_preset input")?.value?.trim().toLowerCase();
    return value && LORA_ARCH_LABELS.has(value) ? value : null;
}

// 0 = matches the preset, 1 = unknown architecture (or no filter), 2 = another architecture.
function loraArchRank(arch, preset) {
    if (!preset || !arch || arch.size === 0) return 1;
    return arch.has(preset) ? 0 : 2;
}

class LoraParser extends BaseTagParser {
    parse() {
        // Show lora
        let tempResults = [];
        // Determine search term:
        // - "<lora:X" or "<l:X" -> search term is X
        // - "<" / "<l" / "<lo" / "<lor" / "<lora" -> user still typing the prefix, show all
        // - "<X" (other) -> direct search for X
        let searchTerm;
        if (tagword.startsWith("<lora:")) {
            searchTerm = tagword.slice("<lora:".length);
        } else if (tagword.startsWith("<l:")) {
            searchTerm = tagword.slice("<l:".length);
        } else {
            const raw = tagword.slice(1); // strip leading "<"
            // If raw is a prefix of "lora" the user is still typing the keyword -> show all
            searchTerm = "lora".startsWith(raw) ? "" : raw;
        }
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
        const preset = currentLoraArchPreset();
        const hideOthers = TAC_CFG.loraArchFilter === "Hide other architectures";
        let finalResults = [];
        tempResults.forEach(t => {
            const archRank = loraArchRank(t[3], preset);
            if (archRank === 2 && hideOthers) return;

            const text = t[0].trim();
            let lastDot = text.lastIndexOf(".") > -1 ? text.lastIndexOf(".") : text.length;
            let lastSlash = text.lastIndexOf("/") > -1 ? text.lastIndexOf("/") : -1;
            let name = text.substring(lastSlash + 1, lastDot);

            let result = new AutocompleteResult(name, ResultType.lora)
            result.meta = "Lora";
            // With the filter on, name every architecture that is not the preset's
            // (others only survive "Show matching first"), and mark unknown ones.
            if (archRank === 2) result.meta += LORA_ARCH_SEPARATOR + [...t[3]].join("/");
            else if (archRank === 1 && preset) result.meta += LORA_ARCH_SEPARATOR + "unknown";
            result.sortKey = t[1];
            result.hash = t[2];
            result.archRank = archRank;
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
            // Column 5: architectures joined with "|", empty when unknown (missing in old files)
            loras = rows.map(x => [x[0]?.trim(), x[1], x[2], new Set((x[4]?.trim() || "").split("|").filter(Boolean))]);
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
