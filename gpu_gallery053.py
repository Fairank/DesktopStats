"""Demand-only index and exact appearance for the independent 2-D GPU gallery.

This browser does not select installed hardware or change the widget's
same-chip picker. No SVG, sensor, optional library or scene is built here.
"""
from copy import deepcopy
import re


_ID = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*\Z', re.ASCII)


def choices():
    """Copy only the existing light GPU index, without resolving appearances."""
    from hardware_appearance import BRANDS, CATALOG
    return [dict(id=row[0], label=row[4], brand=BRANDS[row[3]][0],
                 fidelity='two_dimensional_reference')
            for row in CATALOG if row[1] == 'gpu']


def reference(model_id):
    """Resolve one existing exact model; never repair an ambiguous identity.

    Fan-profile nulls, source evidence and partial board details remain intact.
    Model confidence identifies the selected reference, not the user's GPU.
    """
    if (not isinstance(model_id, str) or len(model_id) > 64
            or not _ID.fullmatch(model_id)):
        return {}
    from hardware_appearance import BRANDS, CATALOG, appearance_for
    row = next((row for row in CATALOG
                if row[1] == 'gpu' and row[0] == model_id), None)
    if row is None:
        return {}
    appearance = appearance_for('gpu', row[-1][0])
    if (appearance.get('kind') != 'gpu' or appearance.get('id') != model_id
            or appearance.get('confidence') != 'model'):
        return {}
    return deepcopy(dict(id=model_id, label=row[4], brand=BRANDS[row[3]][0],
                         appearance=appearance, source_url=row[8],
                         fidelity='two_dimensional_reference',
                         reference_only=True, telemetry_bound=False,
                         installed_model_verified=False,
                         mechanical_fit_verified=False))
