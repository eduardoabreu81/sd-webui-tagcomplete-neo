<div align="center">

# 🏷️ Tag Autocomplete Neo

[![Forge Neo](https://img.shields.io/badge/Forge-Neo-blue)](https://github.com/Haoming02/sd-webui-forge-classic/tree/neo)
[![License](https://img.shields.io/github/license/eduardoabreu81/sd-webui-tagcomplete-neo)](LICENSE)

**Tag autocompletion for [Stable Diffusion WebUI Forge - Neo](https://github.com/Haoming02/sd-webui-forge-classic/tree/neo)**

> ⚠️ **This is a fork** of the original [a1111-sd-webui-tagcomplete](https://github.com/DominikDoom/a1111-sd-webui-tagcomplete) by [DominikDoom](https://github.com/DominikDoom), maintained here exclusively for Forge Neo. **If you are not running Forge Neo, use the [original extension](https://github.com/DominikDoom/a1111-sd-webui-tagcomplete) instead.**

</div>

---

## 📋 Table of Contents

- [What's New](#-whats-new)
- [Roadmap](#️-roadmap)
- [Features](#-features)
- [Installation](#-installation)
- [Tag Lists](#-tag-lists)
- [Credits](#-credits)

---

## 🆕 What's New

> *No stable release yet. Development is in progress — see Roadmap below.*

---

## 🗺️ Roadmap

### v0.1.0 — Forge Neo Baseline (planned)

Makes the extension load and work correctly on Forge Neo.

- Full compatibility with Forge Neo (no more crashes or silent failures on startup)
- Booru tag suggestions showing correctly in the prompt box
- Autocomplete initializing reliably on every WebUI launch
- Embeddings reloading instantly without restarting the WebUI
- Extension surviving Forge updates without breaking
- Settings panel working correctly with the **Apply settings** button
- LoRA trigger words: option to fetch automatically from CivitAI ⭐
- LoRA trigger words: new **"After LoRA/LyCO"** insertion position ⭐
- LoRA trigger word lookup cached by file hash — re-fetched only when the model changes ⭐

### v0.2.0 — Tag Data Update (planned)

Refreshed tag lists for modern models.

- Updated Danbooru and e621 tag lists with current data
- Better tag coverage for Pony, NoobAI, and Illustrious-based models
- Fix for frequency database failing to create on first run

### v0.3.0 — UX Improvements (planned)

Quality-of-life improvements from the most-requested community suggestions.

- Sort suggestions by relevance to tags already in the prompt
- Use multiple tag list files at the same time

### v0.4.0 — Smart Matching (planned)

Smarter completion that requires less typing.

- Fuzzy matching — type abbreviations like `detco` to find `detached_collar`
- Automatically switch tag list based on the currently loaded model

### v1.0.0 — First Stable Release (planned)

- All known bugs resolved
- Full Forge Neo compatibility guarantee

---

## 🎯 Features

> ⭐ = added or fixed in this Neo fork · everything else is original work by [DominikDoom](https://github.com/DominikDoom)

### 🏷️ Tag Autocompletion

- Instant suggestions as you type, sourced from Danbooru, e621, or merged lists
- Keyboard navigation (arrow keys, Tab, Enter, Escape — fully configurable)
- Tags color-coded by category, with post count shown for relevance
- Alias and translation search support
- Remembers your most-used tags and promotes them to the top ⭐

### ➕ Extra Networks

- LoRA and LyCORIS autocomplete, triggered by typing `<`
- Textual Inversion (embedding) autocomplete
- Thumbnail preview in the completion popup
- Automatic trigger word insertion when selecting a LoRA
  - Fetches trigger words from CivitAI if not set locally ⭐
  - Cached per model — only re-fetched when the file itself changes ⭐
  - Configurable insertion position: Start, End, Before or After the LoRA token ⭐
- Filter by type: `<e:` for embeddings, `<l:` for LoRA/LyCORIS

### ✳️ Wildcards

- Autocomplete for wildcard files, triggered by `__`
- Nested folder support
- YAML wildcard format (UMI-compatible)

### 🪄 Chants

- Completion for prompt presets stored in JSON files
- Triggered by `<c:` or `<chant:`

### ⚙️ Settings

All settings are in **Forge Settings → Tag Autocomplete**:

| Setting | Default | Description |
|---|---|---|
| Tag filename | `danbooru.csv` | Active tag list |
| Enable Tag Autocompletion | ON | Master switch |
| Active in txt2img | ON | Enable in txt2img tab |
| Active in img2img | ON | Enable in img2img tab |
| Active in negative prompts | ON | Enable in negative fields |
| Maximum results | 5 | Entries shown in popup |
| Replace underscores with spaces | ON | Inserts `long hair` instead of `long_hair` |
| Escape parentheses on insertion | ON | Inserts `\(` and `\)` correctly |
| Append comma on insertion | ON | Adds `, ` after each tag automatically |
| Frequency sorting | ON | Promotes frequently-used tags to the top |
| Search for LoRAs | ON | Include LoRA names in `<` completion |
| Search for embeddings | ON | Include embedding names in `<` completion |
| Show extra network previews | ON | Thumbnail in popup |
| Try to add trigger words | Never | Inject LoRA trigger words automatically |
| Fetch trigger words from CivitAI | OFF | Look up trigger words online if not set locally ⭐ |
| CivitAI API key | *(blank)* | Optional — only needed for early-access models ⭐ |
| Trigger word insertion position | Start of prompt | Where to place the trigger words ⭐ |

---

## 📦 Installation

1. Open Forge Neo WebUI
2. Go to **Extensions → Install from URL**
3. Paste: `https://github.com/eduardoabreu81/sd-webui-tagcomplete-neo`
4. Click **Install** and reload the WebUI

**Requirements:** Forge Neo with Python 3.10+ and Gradio 4.39.0+ (both come bundled with Forge Neo).

> ⚠️ This extension **will not work** on Automatic1111 or Forge Classic.

---

## 🗂️ Tag Lists

| File | Source | Best for |
|---|---|---|
| `danbooru.csv` | Danbooru top-100k | Anime models (SD 1.5, SDXL) |
| `e621.csv` | e621 top-100k | Furry / anthro models |
| `danbooru_e621_merged.csv` | Merged + unified categories | Pony, NoobAI, Illustrious |
| `extra-quality-tags.csv` | Curated set | Quality booster tags |
| `EnglishDictionary.csv` | English dictionary | Photorealistic / non-booru models |

To switch lists, change **Tag filename** in **Settings → Tag Autocomplete**.

---

## 📄 Credits

All core functionality was built by [DominikDoom](https://github.com/DominikDoom). This fork adds Forge Neo compatibility and new features on top.
Please consider starring the [original repository](https://github.com/DominikDoom/a1111-sd-webui-tagcomplete). ⭐

- **[a1111-sd-webui-tagcomplete](https://github.com/DominikDoom/a1111-sd-webui-tagcomplete)** — [DominikDoom](https://github.com/DominikDoom)
- **[sd-webui-tagcomplete-neo](https://github.com/eduardoabreu81/sd-webui-tagcomplete-neo)** — [Eduardo Abreu](https://github.com/eduardoabreu81)
- **[Forge Neo](https://github.com/Haoming02/sd-webui-forge-classic/tree/neo)** — [Haoming02](https://github.com/Haoming02)

---

## ☕ Support

If you find this extension helpful, consider:

- ⭐ [Starring the repository](https://github.com/eduardoabreu81/sd-webui-tagcomplete-neo)
- 🐛 [Reporting issues](https://github.com/eduardoabreu81/sd-webui-tagcomplete-neo/issues)
- 📢 Sharing with others
- ☕ [Buy me a coffee](https://ko-fi.com/eduardoabreu81)

---

## 📜 License

MIT — see [LICENSE](LICENSE).

[Report a bug](https://github.com/eduardoabreu81/sd-webui-tagcomplete-neo/issues) · [Request a feature](https://github.com/eduardoabreu81/sd-webui-tagcomplete-neo/issues)