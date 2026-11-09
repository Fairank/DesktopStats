"""Reviewed representative GPU SKUs; this module performs no discovery or I/O.

Only complete product names/SKUs are aliases. Related generations, OC variants,
white editions, liquid coolers and other special editions do not inherit these
fan counts. The source pages/PDF front views were checked for physical fans;
cooling-system names and runtime fan sensors are not evidence of fan count.
"""

# id, kind, silicon vendor, board brand, label, style, fans, shroud, URL, aliases
CATALOG_EXTENSIONS = (
    # Official specification: three Axial-tech fans (the O24G OC edition only).
    ("asus-rog-strix-4090-oc", "gpu", "nvidia", "asus",
     "ASUS ROG Strix GeForce RTX 4090 OC Edition 24GB GDDR6X",
     "gpu_axial", 3, "angular",
     "https://rog.asus.com/graphics-cards/graphics-cards/rog-strix/rog-strix-rtx4090-o24g-gaming-model/",
     ("ROG-STRIX-RTX4090-O24G-GAMING",
      "ASUS ROG Strix GeForce RTX 4090 OC Edition 24GB GDDR6X",
      "ROG Strix GeForce RTX 4090 OC Edition 24GB GDDR6X")),
    # Official product datasheet front view: three fans; SUPRIM X, not LIQUID.
    ("msi-suprim-x-4090-24g", "gpu", "nvidia", "msi",
     "MSI GeForce RTX 4090 SUPRIM X 24G", "gpu_axial", 3, "angular",
     "https://www.msi.com/Graphics-Card/GeForce-RTX-4090-SUPRIM-X-24G/Overview",
     ("MSI GeForce RTX 4090 SUPRIM X 24G", "GeForce RTX 4090 SUPRIM X 24G")),
    # Official front view: three fans. Specification identifies G5080-16GT;
    # G5080-16GTC / GAMING TRIO OC is a distinct model and is not an alias.
    ("msi-gaming-trio-5080-16g", "gpu", "nvidia", "msi",
     "MSI GeForce RTX 5080 16G GAMING TRIO", "gpu_axial", 3, "angular",
     "https://www.msi.com/Graphics-Card/GeForce-RTX-5080-16G-GAMING-TRIO/Specification",
     ("G5080-16GT", "MSI GeForce RTX 5080 16G GAMING TRIO",
      "GeForce RTX 5080 16G GAMING TRIO")),
    # Official WINDFORCE description: three 110 mm bionic shark fans.
    ("gigabyte-aorus-4090-master", "gpu", "nvidia", "gigabyte",
     "GIGABYTE AORUS GeForce RTX 4090 MASTER 24G", "gpu_axial", 3, "angular",
     "https://www.gigabyte.com/Graphics-Card/GV-N4090AORUS-M-24GD",
     ("GV-N4090AORUS M-24GD",
      "GIGABYTE AORUS GeForce RTX 4090 MASTER 24G",
      "AORUS GeForce RTX 4090 MASTER 24G")),
    # Official WINDFORCE description: three 110 mm unique blade fans.
    ("gigabyte-aero-4090-oc", "gpu", "nvidia", "gigabyte",
     "GIGABYTE GeForce RTX 4090 AERO OC 24G", "gpu_axial", 3, "box",
     "https://www.gigabyte.com/Graphics-Card/GV-N4090AERO-OC-24GD",
     ("GV-N4090AERO OC-24GD",
      "GIGABYTE GeForce RTX 4090 AERO OC 24G",
      "GeForce RTX 4090 AERO OC 24G")),
    # Official Tri-X description: a trio of fans. SKU excludes PhantomLink.
    ("sapphire-nitro-9070xt-oc", "gpu", "amd", "sapphire",
     "SAPPHIRE NITRO+ AMD Radeon RX 9070 XT OC 16GB GDDR6",
     "gpu_axial", 3, "box",
     "https://www.sapphiretech.com/en/consumer/nitro-radeon-rx-9070-xt-16g-gddr6",
     ("11348-01-20G", "SAPPHIRE NITRO+ AMD Radeon RX 9070 XT OC GPU",
      "SAPPHIRE NITRO+ AMD Radeon RX 9070 XT OC 16GB GDDR6")),
    # Official product front/exploded views: three physical fans. Exact standard
    # SKU only; /WHITE, SAKURA and SAKURA LIMITED are separate products.
    ("powercolor-hellhound-7800xt-oc", "gpu", "amd", "powercolor",
     "PowerColor Hellhound AMD Radeon RX 7800 XT 16GB GDDR6",
     "gpu_axial", 3, "soft",
     "https://www.powercolor.com/product-detail31.htm",
     ("RX7800XT 16G-L/OC",
      "PowerColor Hellhound AMD Radeon RX 7800 XT 16GB GDDR6",
      "Hellhound AMD Radeon RX 7800 XT 16GB GDDR6")),
    # Official product front/exploded views: three physical fans. /LIMITED and
    # /BP model suffixes are not interchangeable with the standard E/OC SKU.
    ("powercolor-red-devil-7800xt-oc", "gpu", "amd", "powercolor",
     "PowerColor Red Devil AMD Radeon RX 7800 XT 16GB GDDR6",
     "gpu_axial", 3, "angular",
     "https://www.powercolor.com/product-detail32.htm",
     ("RX7800XT 16G-E/OC",
      "PowerColor Red Devil AMD Radeon RX 7800 XT 16GB GDDR6",
      "Red Devil AMD Radeon RX 7800 XT 16GB GDDR6")),
)

MODEL_SERIES = {
    "asus-rog-strix-4090-oc": "asus_rog_strix",
    "msi-suprim-x-4090-24g": "msi_suprim",
    "msi-gaming-trio-5080-16g": "msi_gaming",
    "gigabyte-aorus-4090-master": "gigabyte_aorus",
    "gigabyte-aero-4090-oc": "gigabyte_aero",
    "sapphire-nitro-9070xt-oc": "sapphire_nitro",
    "powercolor-hellhound-7800xt-oc": "powercolor_hellhound",
    "powercolor-red-devil-7800xt-oc": "powercolor_red_devil",
}
