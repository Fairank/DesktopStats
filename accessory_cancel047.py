"""Pure cooperative graphics cancellation; no GUI, store or thread creation."""


class ArtCancelled(Exception):
    """An obsolete graphics task must not commit a substitute model."""


def checkpoint(cancel):
    if cancel is not None and cancel.is_set():raise ArtCancelled()
