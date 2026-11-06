"""Exact, source-reviewed group C exteriors; offline illustration metadata.

Only the listed complete SKU can select a recipe. Source photographs establish
the enclosure/fan finish; vector curvature, mesh density and projection remain
illustration estimates. Factory rear plates and supplied removable accessories
are separate views. Neither a lit marketing photo nor a bundled Devil Skin
establishes the user's current LED state or installed accessory. No discovery,
I/O, clock, hidden circuit reconstruction or internal PCB dimensions occur here.
"""


def _fan(technology, label, blades, shape, tone, hub_tone, source_url, *,
         outer_ring=False, hub_ratio=.30, evidence="official_front_view", fans=(), hub_mark=""):
    return dict(technology=technology, label=label, blades=blades, shape=shape,
                tone=tone, hub_tone=hub_tone, hub_ratio=hub_ratio, hub_shape="circle",
                hub_mark=hub_mark, outer_ring=outer_ring, group_size=1, direction=1,
                fans=fans, source_url=source_url, evidence=evidence)


def _gpu(recipe, dimensions, slots, tone, fan_count, fan_profile, *,
         generation=4, lanes=16, ports=None, power=None, pcb_tone="unknown",
         power_position="top", backplate_recipe="", accessory_backplate_recipe="",
         accessory_backplate_label=""):
    return dict(recipe=recipe, style="gpu_axial", fan_count=fan_count,
                visible_fan_count=fan_count, shroud_tone=tone, pcb_tone=pcb_tone,
                dimensions_mm=dict(zip(("length", "height", "thickness"), dimensions)),
                slot_width=slots, fan_profile=fan_profile, backplate=True,
                host_interface=dict(bus="pcie", generation=generation, lanes=lanes,
                                    connector_shape="pcie_standard"),
                ports=ports if ports is not None else ({"type": "HDMI", "count": 1}, {"type": "DP", "count": 3}),
                power_connectors=power if power is not None else ({"type": "8pin", "count": 2},),
                power_position=power_position, pcb_length="unknown", port_layout="unknown",
                backplate_recipe=backplate_recipe,
                accessory_backplate_recipe=accessory_backplate_recipe,
                accessory_backplate_label=accessory_backplate_label)


def _nitro(recipe, height, tone, rotor_tone, hub_tone, source, *, phantom=False,
           hub_mark="", rear=""):
    row = _gpu(recipe, (330.8, height, 65.68), 3.2, tone, 3,
        _fan("sapphire_aerocurve", "AeroCurve · 7叶宽弧环扇", 7, "wide", rotor_tone,
             hub_tone, source, outer_ring=True, hub_mark=hub_mark),
        generation=5, ports=({"type": "HDMI", "count": 2}, {"type": "DP", "count": 2}),
        power=({"type": "16pin", "count": 1},), power_position="alternative" if phantom else "hidden",
        backplate_recipe=rear)
    if phantom:
        row.update(extra_power_interface="gc_hpwr", power_layout=dict(mode="alternative"))
    return row


def _hellhound(recipe, source, *, sakura=False):
    return _gpu(recipe, (322, 134, 50), 2.5, "light", 3,
        _fan("powercolor_ring", "Ring-fan Blade · 9叶", 9, "swept", "light", "light", source,
             outer_ring=True, evidence="explicit_count",
             fans=({"direction": 1}, {"direction": -1}, {"direction": 1})),
        pcb_tone="light", backplate_recipe="c_hellhound_sakura_back" if sakura else "c_hellhound_white_back")


def _devil(recipe, source, accessory):
    return _gpu(recipe, (332, 135, 52), 2.5, "dark", 3,
        _fan("powercolor_ring", "Ring-fan Blade · 9叶", 9, "swept", "dark", "dark", source,
             outer_ring=True, evidence="explicit_count"),
        backplate_recipe="c_devil_factory_back", accessory_backplate_recipe=accessory,
        accessory_backplate_label="附送可拆卸背板；图示不代表当前已安装")


ART = {
    "sapphire-nitro-9070xt-phantomlink": _nitro(
        "c_nitro_phantom", 141.25, "silver", "dark", "silver",
        "https://www.sapphiretech.com/en/consumer/nitro-radeon-rx-9070-xt-ple-16g-gddr6",
        phantom=True, rear="c_nitro_phantom_back"),
    "sapphire-nitro-9070xt-phantomlink-polar": _nitro(
        "c_nitro_polar", 141.75, "light", "light", "silver",
        "https://www.sapphiretech.com/en/consumer/nitro-radeon-rx-9070-xt-ple-polar-16g-gddr6",
        phantom=True, rear="c_nitro_polar_back"),
    "sapphire-nitro-9070xt-valor-mortis": _nitro(
        "c_nitro_valor", 128.5, "silver", "dark", "dark",
        "https://www.sapphiretech.com/en/consumer/nitro-radeon-rx-9070-xt-vme-16g-gddr6",
        hub_mark="gold", rear="c_nitro_valor_back"),
    "sapphire-nitro-9070xt-crimson-desert": _nitro(
        "c_nitro_crimson", 128.5, "silver", "dark", "dark",
        "https://www.sapphiretech.com/en/consumer/nitro-radeon-rx-9070-xt-cde-16g-gddr6",
        hub_mark="gold", rear="c_nitro_crimson_back"),
    "powercolor-hellhound-7800xt-sakura-limited": _hellhound(
        "c_hellhound_sakura_limited", "https://powercolor.com/product-detail34.htm", sakura=True),
    "powercolor-hellhound-7800xt-sakura": _hellhound(
        "c_hellhound_sakura", "https://powercolor.com/product-detail35.htm", sakura=True),
    "powercolor-hellhound-7800xt-white": _hellhound(
        "c_hellhound_white", "https://powercolor.com/product-detail36.htm"),
    "powercolor-red-devil-7800xt-limited": _devil(
        "c_devil_limited", "https://powercolor.com/product-detail39.htm", "c_devil_le_skin"),
    "powercolor-red-devil-7800xt-bp": _devil(
        "c_devil_bp", "https://powercolor.com/product-detail256.htm", "c_devil_intrusive_skin"),
    "powercolor-fighter-7800xt-mini": _gpu(
        "c_fighter_mini", (260, 109, 50), 2.5, "dark", 2,
        _fan("powercolor_ring_mini", "Ring-fan Blade · 9叶", 9, "swept", "dark", "dark",
             "https://powercolor.com/cn/product-detail37.htm", outer_ring=True,
             hub_ratio=.32, evidence="explicit_count"),
        backplate_recipe="c_fighter_mini_back"),
    "sparkle-b580-roc-luna-12g-oc-ultra": _gpu(
        "c_roc_luna", (230, 128, 44), 2.2, "light", 2,
        dict(_fan("sparkle_roc_fdb", "ROC Luna · 11叶宽弧 FDB", 11, "wide", "light", "light",
             "https://www.sparkle.com.tw/en/B580-ROC-Luna",
             hub_ratio=.31, evidence="official_front_view"),
             source_image_url="https://www.sparkle.com.tw/files/20250519102004865.png",
             notes="Exact SB580RW-12GOC official 2000px straight-on photograph: each rotor has eleven broad swept leaves and a white cap. A rotating continuous tip band is not conclusively established, so it is not asserted. Hub ratio/curvature are illustration estimates."),
        lanes=8, backplate_recipe="c_roc_luna_back"),
}
