"""Exact manufacturer mounting facts; nominal fan size is not hole spacing."""
_FACTS={
    'noctua-nf-a12x25-pwm':(105.,None,'https://www.noctua.at/en/products/nf-a12x25-pwm/specifications'),
    'noctua-nf-a14-pwm':(124.5,None,'https://www.noctua.at/en/products/nf-a14-pwm/specifications'),
    'noctua-nf-a14x25-g2-pwm':(124.5,None,'https://www.noctua.at/en/products/nf-a14x25-g2-pwm/specifications'),
    'noctua-nf-a15-pwm':(105.,None,'https://www.noctua.at/en/products/nf-a15-pwm'),
    'arctic-p12-pwm':(105.,4.4,'https://support.arctic.de/products/p12-pwm/techdocs/P12%20Series%20-%202D%20Drawing.pdf'),
}


def apply_mounting_facts(row):
    if not row:return row
    row.update(mount_pitch_mm=None,mount_pitch_verified=False,mount_hole_diameter_mm=None,
               mount_hole_diameter_verified=False)
    if row['id'] in _FACTS:
        pitch,hole,source=_FACTS[row['id']]
        row.update(mount_pitch_mm=pitch,mount_pitch_verified=True,mount_hole_diameter_mm=hole,
                   mount_hole_diameter_verified=hole is not None,mounting_source=source)
        if source not in row['sources']:row['sources'].append(source)
    return row
