"""Tell which model architecture a LoRA / LyCORIS / LoKr file was trained for.

Only the safetensors header is read: tensor names, shapes and __metadata__.
The answer is a set of labels. Most labels are Forge Neo UI preset names
(modules_forge/presets.py); a few name architectures that have no built-in
preset (fibo2, flux3, h3, ideogram4, yue2) so they can still be recognised. An empty set
means unknown. A set with more than one label means the header cannot tell
those architectures apart, and the LoRA belongs with each of them.

Order of sources, first decisive one wins:
  1. The user's own "sd version" from Forge's metadata editor (<lora>.json).
  2. The key fingerprint: every block-level module must be explained by one
     family's names, and the widths of its probe layers must match.
  3. Training metadata, only when the fingerprint gives nothing, or to narrow
     an ambiguous fingerprint.

No network, no torch: this module must stay importable on its own.
"""

import json
import re
import struct
from pathlib import Path

# Bump when the rules change, so cached results are recomputed.
CLASSIFIER_VERSION = 5

MAX_HEADER = 100 * 1024 * 1024


def read_safetensors_header(path: Path):
    """Return (tensors, metadata) from a safetensors header.

    tensors maps each tensor name to its shape; metadata is the __metadata__
    dict (empty if absent). Tensor data is never read.
    """
    with open(path, "rb") as f:
        raw = f.read(8)
        if len(raw) < 8:
            raise ValueError("file shorter than 8 bytes")
        length = struct.unpack("<Q", raw)[0]
        if length > MAX_HEADER:
            raise ValueError(f"header length {length} too large")
        header = json.loads(f.read(length))
    metadata = header.pop("__metadata__", None) or {}
    tensors = {k: v.get("shape") for k, v in header.items() if isinstance(v, dict)}
    return tensors, metadata


# --- Key normalisation -------------------------------------------------------

# Adapter suffix after the module name: (adapter kind, regex).
_SUFFIXES = [
    ("lora", re.compile(r"[._](lora_up|lora_down|lora_mid)\.weight$")),
    ("lora", re.compile(r"\.(lora_A|lora_B)(?:\.default)?(?:\.weight)?$")),
    ("lora", re.compile(r"\.lora\.(up|down)\.weight$")),
    ("lora", re.compile(r"_lora\.(up|down)\.weight$")),
    ("lora", re.compile(r"\.lora_linear_layer\.(up|down)\.weight$")),
    ("lokr", re.compile(r"\.(lokr_w1|lokr_w2|lokr_w1_a|lokr_w1_b|lokr_w2_a|lokr_w2_b|lokr_t2)$")),
    ("loha", re.compile(r"\.(hada_w1_a|hada_w1_b|hada_w2_a|hada_w2_b|hada_t1|hada_t2)$")),
    ("oft", re.compile(r"\.(oft_blocks|rescale|oft_R\.weight)$")),
    ("glora", re.compile(r"\.(a1|a2|b1|b2)\.weight$")),
    ("other", re.compile(r"\.(alpha|dora_scale|diff|diff_b|set_weight|w_norm|b_norm|reshape_weight)$")),
]

_PREFIXES = (
    "model.diffusion_model.",
    "diffusion_model.",
    "base_model.model.",
    "transformer.",
    "unet.",
    "lora_unet_",
    "lora_transformer_",
    "lycoris_",
)

_TEXT_ENCODER = re.compile(r"^(lora_te\d*_|text_encoders?(_\d+)?\.|te\d?\.)")

# A module inside a numbered block (or layer, or refiner). Only these must be
# explained by a family; top-level modules (img_in, final_layer, ...) vary too
# much between trainers to be useful.
_BLOCK = re.compile(r"^(?:.*\.)?(?:blocks|layers|block|refiner)\.\d+(?:\.|$)")


def _canon(name: str) -> str:
    # Kohya flattens dots to underscores, so compare with both as dots.
    return name.replace("_", ".")


def _split(key: str):
    """Return (module, adapter kind, part) or None for a non-adapter key."""
    for kind, rx in _SUFFIXES:
        m = rx.search(key)
        if m:
            return key[: m.start()], kind, m.group(0).lstrip("._")
    return None


def _strip_prefixes(module: str) -> str:
    changed = True
    while changed:
        changed = False
        for p in _PREFIXES:
            if module.startswith(p):
                module = module[len(p):]
                changed = True
    return module


def _widths(parts: dict):
    """(out, in) of the weight the adapter patches; either may be None."""
    def find(*names):
        for n in names:
            if parts.get(n):
                return parts[n]
        return None

    try:
        up = find("lora_up.weight", "lora_B.weight", "lora_B.default.weight", "lora_B", "lora.up.weight", "up.weight")
        down = find("lora_down.weight", "lora_A.weight", "lora_A.default.weight", "lora_A", "lora.down.weight",
                    "down.weight")
        if up or down:
            return (up[0] if up else None, down[1] if down and len(down) > 1 else None)
        w1 = parts.get("lokr_w1")
        if w1 is None and parts.get("lokr_w1_a") and parts.get("lokr_w1_b"):
            w1 = [parts["lokr_w1_a"][0], parts["lokr_w1_b"][1]]
        w2 = parts.get("lokr_w2")
        if w2 is None and parts.get("lokr_w2_a") and parts.get("lokr_w2_b"):
            w2 = [parts["lokr_w2_a"][0], parts["lokr_w2_b"][1]]
        if w1 and w2:
            return (w1[0] * w2[0], w1[1] * w2[1])
        a, b = parts.get("hada_w1_a"), parts.get("hada_w1_b")
        if a or b:
            return (a[0] if a else None, b[1] if b else None)
        full = parts.get("diff")
        if full and len(full) == 2:
            return (full[0], full[1])
    except (IndexError, TypeError):
        pass
    return None


def _modules(tensors: dict):
    """Group adapter tensors by module.

    Returns (blocks, top, text_encoder): blocks and top map canonical
    block-level and top-level module names to their (out, in) widths (or
    None); text_encoder maps raw text-encoder module names to theirs.
    """
    grouped = {}
    for key, shape in tensors.items():
        split = _split(key)
        if split is None:
            continue
        module, _kind, part = split
        grouped.setdefault(module, {})[part] = shape

    blocks, top, text_encoder = {}, {}, {}
    for module, parts in grouped.items():
        if _TEXT_ENCODER.match(module):
            text_encoder[module] = _widths(parts)
            continue
        name = _canon(_strip_prefixes(module))
        (blocks if _BLOCK.match(name) else top)[name] = _widths(parts)
    return blocks, top, text_encoder


# --- Families ----------------------------------------------------------------

def _p(pattern: str) -> re.Pattern:
    """Compile a name pattern written in natural form.

    '.' and '_' both match a canonical dot, '#' is a block index, '*' is any
    text; regex groups and alternation pass through.
    """
    out = []
    for ch in pattern:
        if ch in "._":
            out.append(r"\.")
        elif ch == "#":
            out.append(r"\d+")
        elif ch == "*":
            out.append(".*")
        else:
            out.append(ch)
    return re.compile("".join(out))


class _Variant:
    def __init__(self, probes, max_blocks=None):
        # probes: (pattern, out, in) with None for "any"
        self.probes = [(_p(p), o, i) for p, o, i in probes]
        # max_blocks: {container pattern ending in '(#)': highest count}
        self.max_blocks = [(re.compile(_p(c).pattern.replace(r"\d+", r"(\d+)") + r"(?:\.|$)"), n)
                           for c, n in (max_blocks or {}).items()]

    def accepts(self, blocks: dict, names_only: bool) -> bool:
        checked = False
        for name, w in blocks.items():
            for rx, out, inn in self.probes:
                if not rx.fullmatch(name) or w is None:
                    continue
                if out is not None and w[0] is not None:
                    if w[0] != out:
                        return False
                    checked = True
                if inn is not None and w[1] is not None:
                    if w[1] != inn:
                        return False
                    checked = True
            for rx, limit in self.max_blocks:
                m = rx.match(name)
                if m and int(m.group(1)) >= limit:
                    return False
        # Names alone are not enough: a family is assigned only when at least
        # one probe width confirmed it (Ideogram 4 has Lumina's names).
        return checked or names_only


class _Family:
    def __init__(self, label, names, variants, names_only=False):
        self.label = label
        self.names = re.compile("|".join(f"(?:{_p(n).pattern})" for n in names))
        self.variants = variants
        self.names_only = names_only

    def matches(self, blocks: dict) -> bool:
        if not all(self.names.fullmatch(n) for n in blocks):
            return False
        return any(v.accepts(blocks, self.names_only) for v in self.variants)


_UNET = ["(input_blocks|middle_block|output_blocks|down_blocks|mid_block|up_blocks).#*"]

_FLUX_DOUBLE = [
    "double_blocks.#.(img|txt)_attn.(qkv|proj)",
    "double_blocks.#.(img|txt)_attn.norm.(query|key)_norm",
    "double_blocks.#.(img|txt)_mlp.(0|2)",
]
_FLUX_SINGLE = ["single_blocks.#.(linear1|linear2)", "single_blocks.#.norm.(query|key)_norm"]
_DIFFUSERS_JOINT_ATTN = (
    "transformer_blocks.#.attn.(to_q|to_k|to_v|to_out(.#)?|add_q_proj|add_k_proj|add_v_proj|to_add_out"
    "|norm_q|norm_k|norm_added_q|norm_added_k)"
)
_LUMINA_BLOCKS = "(layers|noise_refiner|context_refiner)"
_LUMINA_NAMES = [
    _LUMINA_BLOCKS + ".#.attention.(qkv|out|q_norm|k_norm|to_q|to_k|to_v|to_out(.#)?|norm_q|norm_k)",
    _LUMINA_BLOCKS + ".#.feed_forward.(w1|w2|w3)",
    _LUMINA_BLOCKS + ".#.(attention_norm1|attention_norm2|ffn_norm1|ffn_norm2)",
]
_KREA_BLOCKS = "(blocks|txtfusion.layerwise_blocks|txtfusion.refiner_blocks)"
_KREA_DIFFUSERS_BLOCKS = "(transformer_blocks|text_fusion.layerwise_blocks|text_fusion.refiner_blocks)"


def _klein(d, mlp, single_in, double_max, single_max):
    """Flux.2 klein variant: hidden d, SiLU-gated MLP of width mlp."""
    return _Variant(
        [
            ("double_blocks.#.(img|txt)_attn.qkv", 3 * d, d),
            ("double_blocks.#.(img|txt)_attn.proj", d, d),
            ("double_blocks.#.(img|txt)_mlp.0", 2 * mlp, d),
            ("double_blocks.#.(img|txt)_mlp.2", d, mlp),
            ("single_blocks.#.linear1", 3 * d + 2 * mlp, d),
            ("single_blocks.#.linear2", d, single_in),
            ("transformer_blocks.#.attn.(to_q|to_k|to_v|add_q_proj|add_k_proj|add_v_proj)", d, d),
            ("transformer_blocks.#.attn.(to_out(.#)?|to_add_out)", d, d),
            ("transformer_blocks.#.(ff|ff_context).linear_in", 2 * mlp, d),
            ("transformer_blocks.#.(ff|ff_context).linear_out", d, mlp),
            ("single_transformer_blocks.#.attn.to_qkv_mlp_proj", 3 * d + 2 * mlp, d),
            ("single_transformer_blocks.#.attn.to_out", d, single_in),
        ],
        {"double_blocks.#": double_max, "single_blocks.#": single_max,
         "transformer_blocks.#": double_max, "single_transformer_blocks.#": single_max},
    )


def _wan(d):
    return _Variant([
        ("blocks.#.(self_attn|cross_attn).(q|k|v|o)", d, d),
        ("blocks.#.cross_attn.(k_img|v_img)", d, None),
        ("blocks.#.ffn.0", None, d),
        ("blocks.#.ffn.2", d, None),
    ])


FAMILIES = [
    _Family("sd", _UNET, [_Variant(
        [("*attn2.to_(k|v)", None, 768)],
        {"*transformer_blocks.#": 1},
    )]),
    _Family("xl", _UNET, [_Variant(
        [("*attn2.to_(k|v)", None, 2048)],
        {"*transformer_blocks.#": 10},
    )]),
    _Family(
        "flux",
        _FLUX_DOUBLE + _FLUX_SINGLE + [
            "double_blocks.#.(img|txt)_mod.lin",
            "single_blocks.#.modulation.lin",
            _DIFFUSERS_JOINT_ATTN,
            "transformer_blocks.#.(ff|ff_context).net.(0.proj|2)",
            "transformer_blocks.#.(norm1|norm1_context).linear",
            "single_transformer_blocks.#.attn.(to_q|to_k|to_v|norm_q|norm_k)",
            "single_transformer_blocks.#.(proj_mlp|proj_out|norm.linear)",
            # Chroma (a Flux.1 schnell finetune) replaces the guidance input with this network.
            "distilled_guidance_layer.(layers.#.(in_layer|out_layer|linear_1|linear_2)|norms.#)",
        ],
        [_Variant(
            [
                ("double_blocks.#.(img|txt)_attn.qkv", 9216, 3072),
                ("double_blocks.#.(img|txt)_attn.proj", 3072, 3072),
                ("double_blocks.#.(img|txt)_mlp.0", 12288, 3072),
                ("double_blocks.#.(img|txt)_mlp.2", 3072, 12288),
                ("double_blocks.#.(img|txt)_mod.lin", 18432, 3072),
                ("single_blocks.#.linear1", 21504, 3072),
                ("single_blocks.#.linear2", 3072, 15360),
                ("single_blocks.#.modulation.lin", 9216, 3072),
                ("transformer_blocks.#.attn.(to_q|to_k|to_v|add_q_proj|add_k_proj|add_v_proj)", 3072, 3072),
                ("transformer_blocks.#.attn.(to_out(.#)?|to_add_out)", 3072, 3072),
                ("transformer_blocks.#.(ff|ff_context).net.0.proj", 12288, 3072),
                ("transformer_blocks.#.(ff|ff_context).net.2", 3072, 12288),
                ("transformer_blocks.#.(norm1|norm1_context).linear", 18432, 3072),
                ("single_transformer_blocks.#.attn.(to_q|to_k|to_v)", 3072, 3072),
                ("single_transformer_blocks.#.proj_mlp", 12288, 3072),
                ("single_transformer_blocks.#.proj_out", 3072, 15360),
                ("single_transformer_blocks.#.norm.linear", 9216, 3072),
                ("distilled_guidance_layer.layers.#.(in_layer|out_layer|linear_1|linear_2)", 5120, 5120),
            ],
            {"double_blocks.#": 19, "single_blocks.#": 38,
             "transformer_blocks.#": 19, "single_transformer_blocks.#": 38},
        )],
    ),
    _Family(
        "klein",
        _FLUX_DOUBLE + _FLUX_SINGLE + [
            _DIFFUSERS_JOINT_ATTN,
            "transformer_blocks.#.(ff|ff_context).(linear_in|linear_out)",
            "single_transformer_blocks.#.attn.(to_qkv_mlp_proj|to_out|norm_q|norm_k)",
        ],
        [_klein(3072, 9216, 12288, 5, 20), _klein(4096, 12288, 16384, 8, 24)],
    ),
    _Family(
        "qwen",
        [
            _DIFFUSERS_JOINT_ATTN,
            "transformer_blocks.#.(img|txt)_mlp.net.(#.proj|#)",
            "transformer_blocks.#.(img|txt)_mod.#",
        ],
        [_Variant(
            [
                ("transformer_blocks.#.attn.(to_q|to_k|to_v|add_q_proj|add_k_proj|add_v_proj)", 3072, 3072),
                ("transformer_blocks.#.attn.(to_out(.#)?|to_add_out)", 3072, 3072),
                ("transformer_blocks.#.(img|txt)_mlp.net.#.proj", 12288, 3072),
                ("transformer_blocks.#.(img|txt)_mlp.net.2", 3072, 12288),
                ("transformer_blocks.#.(img|txt)_mod.#", 18432, 3072),
            ],
            {"transformer_blocks.#": 60},
        )],
    ),
    _Family(
        "qwen21",
        [
            "transformer_blocks.#.attn.(to_q|to_k|to_v|to_out(.#)?|norm_q|norm_k)",
            "transformer_blocks.#.img_mlp.(gate_up|proj|gate_layer|out)",
        ],
        [_Variant(
            [
                ("transformer_blocks.#.attn.(to_q|to_k|to_v|to_out(.#)?)", 4096, 4096),
                ("transformer_blocks.#.img_mlp.gate_up", 24576, 4096),
                ("transformer_blocks.#.img_mlp.(proj|gate_layer)", 12288, 4096),
                ("transformer_blocks.#.img_mlp.out", 4096, 12288),
            ],
            {"transformer_blocks.#": 32},
        )],
    ),
    _Family(
        "lumina",
        _LUMINA_NAMES + ["(layers|noise_refiner).#.adaLN_modulation.1"],
        [_Variant([
            (_LUMINA_BLOCKS + ".#.attention.qkv", 3840, 2304),
            (_LUMINA_BLOCKS + ".#.attention.(out|to_out(.#)?|to_q)", 2304, 2304),
            (_LUMINA_BLOCKS + ".#.attention.(to_k|to_v)", 768, 2304),
            (_LUMINA_BLOCKS + ".#.feed_forward.(w1|w3)", 9216, 2304),
            (_LUMINA_BLOCKS + ".#.feed_forward.w2", 2304, 9216),
            ("(layers|noise_refiner).#.adaLN_modulation.1", None, 1024),
        ])],
    ),
    _Family(
        "zit",
        _LUMINA_NAMES + ["(layers|noise_refiner).#.adaLN_modulation.0"],
        [_Variant([
            (_LUMINA_BLOCKS + ".#.attention.qkv", 11520, 3840),
            (_LUMINA_BLOCKS + ".#.attention.(out|to_out(.#)?|to_q|to_k|to_v)", 3840, 3840),
            (_LUMINA_BLOCKS + ".#.feed_forward.(w1|w3)", 10240, 3840),
            (_LUMINA_BLOCKS + ".#.feed_forward.w2", 3840, 10240),
            ("(layers|noise_refiner).#.adaLN_modulation.0", 15360, 256),
        ])],
    ),
    _Family(
        "wan",
        [
            "blocks.#.(self_attn|cross_attn).(q|k|v|o|norm_q|norm_k)",
            "blocks.#.cross_attn.(k_img|v_img|norm_k_img)",
            "blocks.#.ffn.(0|2)",
            "blocks.#.(norm3|modulation)",
        ],
        [_wan(1536), _wan(3072), _wan(5120)],
    ),
    _Family(
        "anima",
        [
            "blocks.#.(self_attn|cross_attn).(q_proj|k_proj|v_proj|output_proj|q_norm|k_norm)",
            "blocks.#.mlp.(layer1|layer2)",
            "blocks.#.adaln_modulation_(self_attn|cross_attn|mlp).#",
            "blocks.#.layer_norm_(self_attn|cross_attn|mlp)",
            "llm_adapter.blocks.#.(self_attn|cross_attn).(q_proj|k_proj|v_proj|o_proj|q_norm|k_norm)",
            "llm_adapter.blocks.#.mlp.(0|2)",
            "llm_adapter.blocks.#.norm_(self_attn|cross_attn|mlp)",
        ],
        [_Variant([
            ("blocks.#.self_attn.(q_proj|k_proj|v_proj|output_proj)", 2048, 2048),
            ("blocks.#.cross_attn.(q_proj|output_proj)", 2048, 2048),
            ("blocks.#.cross_attn.(k_proj|v_proj)", 2048, 1024),
            ("blocks.#.mlp.layer1", None, 2048),
            ("blocks.#.mlp.layer2", 2048, None),
        ])],
    ),
    _Family(
        "ernie",
        [
            "layers.#.self_attention.(to_q|to_k|to_v|to_out(.#)?|norm_q|norm_k)",
            "layers.#.mlp.(gate_proj|up_proj|linear_fc2)",
            "layers.#.(adaLN_sa_ln|adaLN_mlp_ln)",
        ],
        [_Variant(
            [
                ("layers.#.self_attention.(to_q|to_k|to_v|to_out(.#)?)", 4096, 4096),
                ("layers.#.mlp.(gate_proj|up_proj)", 12288, 4096),
                ("layers.#.mlp.linear_fc2", 4096, 12288),
            ],
            {"layers.#": 36},
        )],
    ),
    # PiD's block containers exist in no other family; its widths are only
    # code defaults, so names alone decide.
    _Family("pid", ["(patch_blocks|pixel_blocks).#*"], [_Variant([])], names_only=True),
    _Family(
        "krea",
        [
            _KREA_BLOCKS + ".#.attn.(wq|wk|wv|wo|gate|qknorm.qnorm|qknorm.knorm)",
            _KREA_BLOCKS + ".#.mlp.(gate|up|down)",
            _KREA_BLOCKS + ".#.(prenorm|postnorm|mod.lin)",
            _KREA_DIFFUSERS_BLOCKS + ".#.attn.(to_q|to_k|to_v|to_gate|to_out(.#)?)",
            _KREA_DIFFUSERS_BLOCKS + ".#.ff.(gate|up|down)",
        ],
        [_Variant(
            [
                ("blocks.#.attn.(wq|wo|gate)", 6144, 6144),
                ("blocks.#.attn.(wk|wv)", 1536, 6144),
                ("blocks.#.mlp.(gate|up)", 16384, 6144),
                ("blocks.#.mlp.down", 6144, 16384),
                ("txtfusion.(layerwise_blocks|refiner_blocks).#.attn.(wq|wk|wv|wo|gate)", 2560, 2560),
                ("txtfusion.(layerwise_blocks|refiner_blocks).#.mlp.(gate|up)", 6912, 2560),
                ("txtfusion.(layerwise_blocks|refiner_blocks).#.mlp.down", 2560, 6912),
                ("transformer_blocks.#.attn.(to_q|to_gate|to_out(.#)?)", 6144, 6144),
                ("transformer_blocks.#.attn.(to_k|to_v)", 1536, 6144),
                ("transformer_blocks.#.ff.(gate|up)", 16384, 6144),
                ("transformer_blocks.#.ff.down", 6144, 16384),
                ("text_fusion.(layerwise_blocks|refiner_blocks).#.attn.(to_q|to_k|to_v|to_gate|to_out(.#)?)",
                 2560, 2560),
                ("text_fusion.(layerwise_blocks|refiner_blocks).#.ff.(gate|up)", 6912, 2560),
                ("text_fusion.(layerwise_blocks|refiner_blocks).#.ff.down", 2560, 6912),
            ],
            {"blocks.#": 28, "transformer_blocks.#": 28},
        )],
    ),
    _Family(
        "moss",
        [
            "layers.#.proj.(qkv|q|k|v|o|ffn_up_gate|ffn_down)",
            "layers.#.(norm1|norm2|q_norm|k_norm)",
            "text_embedder.blocks.#.(qkv|proj|ffn_gate|ffn_up|ffn_down|norm1|norm2|q_norm|k_norm)",
        ],
        [_Variant(
            [
                ("layers.#.proj.qkv", 9216, 3072),
                ("layers.#.proj.(q|k|v|o)", 3072, 3072),
                ("layers.#.proj.ffn_up_gate", 16384, 3072),
                ("layers.#.proj.ffn_down", 3072, 8192),
                ("text_embedder.blocks.#.qkv", 9216, 3072),
                ("text_embedder.blocks.#.proj", 3072, 3072),
                ("text_embedder.blocks.#.(ffn_gate|ffn_up)", 8192, 3072),
                ("text_embedder.blocks.#.ffn_down", 3072, 8192),
            ],
            {"layers.#": 42},
        )],
    ),
    # Architectures without a built-in Forge preset. They match only when an
    # extension adds a preset of the same name (fibo2-forge-neo adds fibo2).
    _Family(
        "fibo2",
        [
            _LUMINA_BLOCKS + ".#.attention.(qkv|out|q_norm|k_norm)",
            _LUMINA_BLOCKS + ".#.(attention_norm1|attention_norm2|ffn_norm1|ffn_norm2|cross_attn_norm1|cross_attn_norm2)",
            _LUMINA_BLOCKS + ".#.feed_forward.(w13|w1|w2|w3)",
            _LUMINA_BLOCKS + ".#.adaLN_modulation.#",
            "layers.#.cross_attention.(to_q|to_kv|to_out|norm_q|norm_k)",
            "perceiver.layers.#.(cross_attention|self_attention).(to_q|to_kv|to_out|norm_q|norm_k)",
            "perceiver.layers.#.(cross_attn_norm|self_attn_norm|ffn_norm)",
            "perceiver.layers.#.ffn.(w13|w2)",
        ],
        [_Variant(
            [
                (_LUMINA_BLOCKS + ".#.attention.qkv", 10752, 3584),
                (_LUMINA_BLOCKS + ".#.attention.out", 3584, 3584),
                (_LUMINA_BLOCKS + ".#.feed_forward.w13", 19456, 3584),
                (_LUMINA_BLOCKS + ".#.feed_forward.w2", 3584, 9728),
                (_LUMINA_BLOCKS + ".#.adaLN_modulation.#", 14336, 256),
                ("*cross_attention.(to_q|to_out)", 3584, 3584),
                ("*(cross_attention|self_attention).to_kv", 7168, None),
            ],
            {"layers.#": 44},
        )],
    ),
    _Family(
        "flux3",
        ["single_blocks.#.(q_proj|k_proj|v_proj|attn_out|mlp_in|mlp_out)"],
        [_Variant(
            [
                ("single_blocks.#.(q_proj|k_proj|v_proj|attn_out)", 3072, 3072),
                ("single_blocks.#.mlp_in", 18432, 3072),
                ("single_blocks.#.mlp_out", 3072, 9216),
            ],
            {"single_blocks.#": 28},
        )],
    ),
    _Family(
        "h3",
        [
            "(blocks|token_refiner.blocks).#.attn.(qkv_proj|out_proj)",
            "(blocks|token_refiner.blocks).#.mlp.(fc1|fc2)",
            "blocks.#.adaln_proj.linear",
        ],
        [_Variant(
            [
                ("(blocks|token_refiner.blocks).#.attn.qkv_proj", 21504, 5376),
                ("(blocks|token_refiner.blocks).#.attn.out_proj", 5376, 7168),
                ("(blocks|token_refiner.blocks).#.mlp.fc1", 28672, 5376),
                ("(blocks|token_refiner.blocks).#.mlp.fc2", 5376, 14336),
                ("blocks.#.adaln_proj.linear", 96768, None),
            ],
            {"blocks.#": 50},
        )],
    ),
    # YuE2, an LLM-based music model: Qwen-style decoder layers (28 x 2048), with
    # a separate non-autoregressive stack (nar_*) in some adapters.
    _Family(
        "yue2",
        [
            "model.layers.#.(self_attn|nar_self_attn).(q_proj|k_proj|v_proj|o_proj)",
            "model.layers.#.(mlp|nar_mlp).(gate_proj|up_proj|down_proj)",
        ],
        [_Variant(
            [
                ("model.layers.#.(self_attn|nar_self_attn).(q_proj|o_proj)", 2048, 2048),
                ("model.layers.#.(self_attn|nar_self_attn).(k_proj|v_proj)", 1024, 2048),
                ("model.layers.#.(mlp|nar_mlp).(gate_proj|up_proj)", 6144, 2048),
                ("model.layers.#.(mlp|nar_mlp).down_proj", 2048, 6144),
            ],
            {"model.layers.#": 28},
        )],
    ),
    _Family(
        "ideogram4",
        ["layers.#.attention.(qkv|o)", "layers.#.feed_forward.(w1|w2|w3)", "layers.#.adaln_modulation"],
        [_Variant(
            [
                ("layers.#.attention.qkv", 13824, 4608),
                ("layers.#.attention.o", 4608, 4608),
                ("layers.#.feed_forward.(w1|w3)", 12288, 4608),
                ("layers.#.feed_forward.w2", 4608, 12288),
                ("layers.#.adaln_modulation", 18432, 512),
            ],
            {"layers.#": 34},
        )],
    ),
]

# Top-level modules, for files that touch no block at all (slider LoRAs often
# change a single conditioning layer). Same rules as FAMILIES: every top-level
# module must fit the names, and a probe width must confirm. Only names seen on
# real files or read in Forge's code are listed; anything else stays unknown.
TOP_FAMILIES = [
    _Family(
        "krea",
        ["first", "tmlp.(0|2)", "txtmlp.(0|1|3)", "tproj.1", "last.(linear|norm|modulation.lin)",
         "txtfusion.projector"],
        [_Variant([
            ("first", 6144, None),
            ("tmlp.0", 6144, None),
            ("tmlp.2", 6144, 6144),
            ("txtmlp.1", 6144, 2560),
            ("txtmlp.3", 6144, 6144),
            ("tproj.1", 36864, 6144),
            ("last.linear", None, 6144),
            ("txtfusion.projector", 1, 12),
        ])],
    ),
    _Family(
        "flux",
        ["img_in", "txt_in", "(time_in|vector_in|guidance_in).(in_layer|out_layer)",
         "final_layer.(linear|adaLN_modulation.1)"],
        [_Variant([
            ("img_in", 3072, 64),
            ("txt_in", 3072, 4096),
            ("(time_in|guidance_in).in_layer", 3072, 256),
            ("vector_in.in_layer", 3072, 768),
            ("(time_in|vector_in|guidance_in).out_layer", 3072, 3072),
            ("final_layer.linear", 64, 3072),
            ("final_layer.adaLN_modulation.1", 6144, 3072),
        ])],
    ),
    _Family(
        "klein",
        ["img_in", "txt_in", "time_in.(in_layer|out_layer)", "final_layer.(linear|adaLN_modulation.1)",
         "double_stream_modulation_(img|txt).lin", "single_stream_modulation.lin"],
        [
            # 4B: only the widths it shares with Flux.1's naming are certain.
            _Variant([
                ("img_in", 3072, 128),
                ("time_in.in_layer", 3072, 256),
                ("time_in.out_layer", 3072, 3072),
                ("final_layer.linear", 128, 3072),
                ("final_layer.adaLN_modulation.1", 6144, 3072),
                ("double_stream_modulation_(img|txt).lin", 18432, 3072),
                ("single_stream_modulation.lin", 9216, 3072),
            ]),
            _Variant([
                ("img_in", 4096, 128),
                ("txt_in", 4096, 12288),
                ("time_in.in_layer", 4096, 256),
                ("time_in.out_layer", 4096, 4096),
                ("final_layer.linear", 128, 4096),
                ("final_layer.adaLN_modulation.1", 8192, 4096),
                ("double_stream_modulation_(img|txt).lin", 24576, 4096),
                ("single_stream_modulation.lin", 12288, 4096),
            ]),
        ],
    ),
    _Family(
        "moss",
        ["video_embedder", "text_embedder.proj", "time_embedding.(0|2)", "shared_block_modulation",
         "video_head_modulation", "final_linear_video"],
        [_Variant([
            ("video_embedder", 3072, 128),
            ("text_embedder.proj", 3072, 4096),
            ("time_embedding.0", 3072, 256),
            ("time_embedding.2", 3072, 3072),
            ("shared_block_modulation", 18432, 3072),
            ("video_head_modulation", 6144, 3072),
            ("final_linear_video", 128, 3072),
        ])],
    ),
    _Family(
        "fibo2",
        ["x_embedder", "t_embedder.mlp.(0|2)", "final_layer.(linear|adaLN_modulation.#)"],
        [_Variant([
            ("x_embedder", 3584, 128),
            ("final_layer.linear", 128, 3584),
            ("final_layer.adaLN_modulation.#", 3584, 256),
        ])],
    ),
    _Family(
        "flux3",
        ["emb_in.image", "(early_stream_modulations|single_stream_modulations).image.lin",
         "final_layer.image.adaLN_modulation.#", "content_mode_blocks.image.#*"],
        [_Variant([
            ("emb_in.image", 3072, 128),
            ("(early_stream_modulations|single_stream_modulations).image.lin", 9216, 3072),
            ("final_layer.image.adaLN_modulation.#", 6144, 3072),
            ("content_mode_blocks.image.#.(q_proj|k_proj|v_proj|attn_out)", 3072, 3072),
            ("content_mode_blocks.image.#.mlp_in", 18432, 3072),
            ("content_mode_blocks.image.#.mlp_out", 3072, 9216),
        ])],
    ),
]

LABELS = frozenset(f.label for f in FAMILIES)


def _from_blocks(blocks: dict) -> frozenset:
    return frozenset(f.label for f in FAMILIES if f.matches(blocks))


def _from_top(top: dict) -> frozenset:
    return frozenset(f.label for f in TOP_FAMILIES if f.matches(top))


def _from_text_encoder(text_encoder: dict) -> frozenset:
    """Only for files with no block-level modules at all."""
    names = list(text_encoder)
    if any(n.startswith(("lora_te_layers_", "lora_te_llm_adapter_")) for n in names):
        return frozenset({"anima"})
    second = [n for n in names if n.startswith(("lora_te2_", "text_encoder_2."))]
    if any("text_model" in n for n in second):
        return frozenset({"xl"})
    if any(re.search(r"encoder[._]block", n) for n in second):
        return frozenset({"flux"})
    if any(n.startswith("lora_te1_") for n in names):
        return frozenset({"xl", "flux"})
    if any(n.startswith("lora_te_text_model") for n in names):
        # SD1 CLIP-L is 768 wide; SD2's OpenCLIP (1024) has no preset.
        outs = {w[0] for w in text_encoder.values() if w and w[0]}
        return frozenset({"sd"}) if outs and outs <= {768, 3072} else frozenset()
    return frozenset()


# (metadata key, value regex, label); checked in this order, first match wins.
_METADATA = [
    ("modelspec.architecture", r"stable-diffusion-xl", "xl"),
    ("modelspec.architecture", r"stable-diffusion-v1", "sd"),
    ("modelspec.architecture", r"flux-1|flux\.1|chroma", "flux"),
    ("modelspec.architecture", r"qwen-image-2", "qwen21"),
    ("modelspec.architecture", r"qwen-image", "qwen"),
    ("modelspec.architecture", r"krea-?2", "krea"),
    ("modelspec.architecture", r"moss-image", "moss"),
    ("ss_base_model_version", r"sdxl", "xl"),
    ("ss_base_model_version", r"sd_v1", "sd"),
    ("ss_base_model_version", r"flux1|flux$|chroma", "flux"),
    ("ss_base_model_version", r"qwen_image_2", "qwen21"),
    ("ss_base_model_version", r"qwen_image", "qwen"),
    ("ss_base_model_version", r"krea2", "krea"),
    ("ss_base_model_version", r"moss_image", "moss"),
    ("ss_base_model_version", r"fibo2", "fibo2"),
    ("ss_base_model_version", r"ideogram4", "ideogram4"),
    ("ss_base_model_version", r"minimax_h3", "h3"),
    ("ss_base_model_version", r"lumina", "lumina"),
    ("ss_base_model_version", r"z_?image", "zit"),
    ("ss_base_model_version", r"wan", "wan"),
    ("ss_base_model_version", r"anima", "anima"),
    ("maltrainer_architecture", r"moss_image", "moss"),
    ("adapter_config", r'.*"format": *"moss-edit-lora"', "moss"),
    ("format", r"fl-yue2", "yue2"),
]


def _from_metadata(metadata: dict):
    if str(metadata.get("ss_v2", "")).lower() == "true":
        return None
    for key, pattern, label in _METADATA:
        value = str(metadata.get(key, "")).lower()
        if value and re.match(pattern, value):
            return label
    return None


# Values Forge's metadata editor (or A1111's) may have saved.
_USER_VALUES = {"sd1": "sd", "sdxl": "xl"}


def user_label(value):
    """Map a user-entered "sd version" to a label, or None to ignore it."""
    if not isinstance(value, str):
        return None
    value = value.strip().lower()
    value = _USER_VALUES.get(value, value)
    if not value or value == "unknown" or not re.fullmatch(r"[a-z0-9_]+", value):
        return None
    return value


def classify(tensors: dict, metadata: dict = None, user_value: str = None) -> frozenset:
    """Return the set of architecture labels for one LoRA header."""
    user = user_label(user_value)
    if user:
        return frozenset({user})

    blocks, top, text_encoder = _modules(tensors)
    if blocks:
        found = _from_blocks(blocks)
    elif top:
        found = _from_top(top)
    else:
        found = _from_text_encoder(text_encoder)

    hint = _from_metadata(metadata or {})
    if not found:
        return frozenset({hint}) if hint else frozenset()
    if len(found) > 1 and hint in found:
        return frozenset({hint})
    return found


def classify_file(path: Path, user_value: str = None) -> frozenset:
    """classify() for a file on disk; unknown on any read error."""
    try:
        tensors, metadata = read_safetensors_header(path)
    except Exception:
        return frozenset()
    return classify(tensors, metadata, user_value)
