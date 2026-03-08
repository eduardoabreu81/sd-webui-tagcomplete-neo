<div align="center">

<img src=".github/banner.png" alt="TagComplete Neo"/>

[![Forge Neo](https://img.shields.io/badge/Forge-Neo-blue)](https://github.com/Haoming02/sd-webui-forge-classic/tree/neo)
[![Gradio](https://img.shields.io/badge/Gradio-4.39.0+-orange)](https://gradio.app/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> **Extension for [Stable Diffusion WebUI Forge - Neo](https://github.com/Haoming02/sd-webui-forge-classic/tree/neo)**

</div>

# 🏷️ TagComplete Neo

Tag autocompletion for Forge Neo — suggests Danbooru/e621 tags, LoRA/embedding names, wildcards, and chants as you type, with automatic trigger word injection and CivitAI lookup support.

Fork of [a1111-sd-webui-tagcomplete](https://github.com/DominikDoom/a1111-sd-webui-tagcomplete) by [DominikDoom](https://github.com/DominikDoom), maintained here exclusively for Forge Neo. If you are not running Forge Neo, use the [original extension](https://github.com/DominikDoom/a1111-sd-webui-tagcomplete) instead.

---

## 📋 Table of Contents

- [What's New](#-whats-new)
- [Changelog](#-changelog)
- [Roadmap](#️-roadmap)
- [Features](#-features)
- [Installation](#-installation)
- [Tag Lists](#-tag-lists)
- [Credits](#-credits)

---

## 🆕 What's New

### v0.1.2 — Bug fix batch

- **Embedding manual refresh no longer crashes** — the `force_reload` kwarg was removed from Forge Neo; the refresh button now works cleanly
- **LoRAs always visible on startup** — the previous alias update inadvertently caused LoRAs to disappear until a model was loaded; filesystem scan is now always used as the primary source
- **Symlinked embeddings supported** — paths are fully resolved before comparison, so embeddings linked from outside the `models/embeddings/` folder no longer crash the callback
- **Frequency database stability** — fixed a potential `NameError` on first run when the SQLite connection itself could not be established

### v0.1.1 — LoRA alias fix

- **LoRA/LyCORIS token no longer blinks** — the inserted `<lora:…>` token now uses the same identifier that Forge Neo expects (respects your "When adding to prompt, refer to LoRA by" setting: *Alias from file* or *Filename*) ⭐

### v0.1.0 — Forge Neo Baseline

- **Full Forge Neo compatibility** — extension loads and runs correctly on Forge Neo without crashes or silent failures
- **Booru tags restored** — tag suggestions now appear correctly in the prompt box
- **Reliable initialization** — autocomplete activates on every WebUI launch, including the second and beyond
- **Instant embedding reload** — embeddings update without restarting the WebUI
- **Trigger word auto-fetch from CivitAI** — if a LoRA has no local trigger words set, the extension can look them up automatically from CivitAI ⭐
- **Trigger word cache by file hash** — fetched words are saved alongside the model and only re-fetched when the file itself changes ⭐
- **"After LoRA/LyCO" insertion position** — new option to place trigger words immediately after the `<lora:…>` token instead of only at the start or end of the prompt ⭐

---

## 📖 Changelog

### v0.1.2 — Bug fix batch
- Embedding manual refresh (`tac_forceRefreshEmbeddings`) no longer throws `TypeError` on Forge Neo
- LoRA list always populated from filesystem scan; `lora.available_loras` used only for alias enrichment
- `get_embeddings()` resolves symlinks before `relative_to()` — no more crash with linked embedding folders
- `transaction()` in frequency DB initialises `conn = None` before `try` block — prevents `NameError` on failed DB creation

### v0.1.1 — LoRA alias fix
- LoRA/LyCORIS completion now inserts the alias Forge Neo expects, eliminating token blink
- Respects the "Alias from file" / "Filename" setting in Extra Networks

### v0.1.0 — Forge Neo Baseline
- Full Forge Neo / Gradio 4 compatibility
- Booru tags, initialization, and embedding reload fixed
- CivitAI trigger word lookup with SHA256 cache
- "After LoRA/LyCO" insertion option

---

## 🗺️ Roadmap

### v0.1.2 — Bug fix batch ✅
- Embedding manual refresh fixed (Forge Neo removed `force_reload` kwarg) ✅
- LoRA list always populated at startup ✅
- Symlinked embeddings no longer crash on model load ✅
- Frequency database `NameError` on first run fixed ✅

### v0.1.1 — LoRA alias fix ✅
- LoRA/LyCORIS token matches Forge Neo's expected alias ✅

### v0.1.0 — Forge Neo Baseline ✅
- Forge Neo / Gradio 4 compatibility ✅
- Booru tag display fixed (Gradio 4 selectors) ✅
- Reliable re-initialization after WebUI reconnect ✅
- Embedding reload hardened ✅
- Extension resilience after Forge updates ✅
- CivitAI trigger word lookup with SHA256 cache ✅
- "After LoRA/LyCO" insertion option ✅

### v0.2.0 — Tag Data Update *(planned)*
- Updated Danbooru and e621 tag lists with current data
- Better tag coverage for Pony, NoobAI, and Illustrious-based models

### v0.3.0 — UX Improvements *(planned)*
- Sort suggestions by relevance to tags already in the prompt
- Use multiple tag list files at the same time

### v0.4.0 — Smart Matching *(planned)*
- Fuzzy matching — type abbreviations like `detco` to find `detached_collar`
- Automatically switch tag list based on the currently loaded model

### v1.0.0 — First Stable Release *(planned)*
- All known issues resolved
- Full Forge Neo compatibility guarantee

---

## 🎯 Features

> ⭐ = added or fixed in this Neo fork · everything else is original work by [DominikDoom](https://github.com/DominikDoom)

### 🏷️ Tag Autocompletion

- **Instant suggestions** as you type, sourced from Danbooru, e621, or merged lists
- **Keyboard navigation** — arrow keys, Tab, Enter, Escape, all configurable
- **Tag color coding** by category, with post count for relevance
- **Alias and translation search** — find tags by their alternate names or translated terms
- **Frequency sorting** — remembers your most-used tags and promotes them to the top ⭐

### ➕ Extra Networks

- **LoRA and LyCORIS autocomplete** triggered by `<`
- **Embedding autocomplete** triggered by `<e:`
- **Thumbnail preview** in the completion popup
- **Correct alias insertion** — uses the same identifier Forge Neo expects (`ss_output_name` or filename, respecting your Extra Networks setting) so tokens never blink ⭐
- **Trigger word injection** on LoRA selection — inserts activation keywords automatically
  - Fetches from CivitAI if not set locally ⭐
  - Cached by SHA256 — only re-fetched when the model file changes ⭐
  - Configurable position: Start of prompt, End of prompt, Before or After the LoRA token ⭐

### ✳️ Wildcards

- **Wildcard file autocomplete** triggered by `__`
- **Nested folder support**
- **YAML wildcard format** (UMI-compatible)

### 🪄 Chants

- **Prompt preset completion** for longer phrase templates stored in JSON files
- Triggered by `<c:` or `<chant:`

---

## 📦 Installation

1. Open Forge Neo WebUI
2. Go to **Extensions** → **Install from URL**
3. Paste: `https://github.com/eduardoabreu81/sd-webui-tagcomplete-neo`
4. Click **Install** and reload the WebUI

> ⚠️ This extension requires **Forge Neo**. It will not work on Automatic1111 or Forge Classic.

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

- **[a1111-sd-webui-tagcomplete](https://github.com/DominikDoom/a1111-sd-webui-tagcomplete)** by DominikDoom — original project, all core functionality
- **[sd-webui-tagcomplete-neo](https://github.com/eduardoabreu81/sd-webui-tagcomplete-neo)** by [Eduardo Abreu](https://github.com/eduardoabreu81) — Forge Neo fork
- **[Forge Neo](https://github.com/Haoming02/sd-webui-forge-classic/tree/neo)** by Haoming02

---

## 📜 License

MIT — see [LICENSE](LICENSE)

---

<div align="center">

Made with ❤️ for the Stable Diffusion community

**[Report Bug](https://github.com/eduardoabreu81/sd-webui-tagcomplete-neo/issues)** • **[Request Feature](https://github.com/eduardoabreu81/sd-webui-tagcomplete-neo/issues)** • **[☕ Ko-fi](https://ko-fi.com/eduardoabreu81)**

</div>