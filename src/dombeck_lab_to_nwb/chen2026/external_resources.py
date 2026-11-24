"""HERD references for the ontology terms listed in metadata/external_resources.yaml.

The YAML file uses the ``ExternalResources`` layout of NeuroConv's ontology guide
(https://neuroconv.readthedocs.io/en/main/user_guide/ontology.html). The NeuroConv release this conversion
runs on (0.10) does not write that block yet, so this module writes the references. They are stored in the
NWB file under ``/general/external_resources`` and read back with ``nwbfile.external_resources.to_dataframe()``.
"""

from hdmf.common import DynamicTable
from pynwb import NWBFile
from pynwb.resources import HERD


def add_external_resources(nwbfile: NWBFile, terms: dict) -> None:
    """Write the terms of the ``ExternalResources`` block into the file as HERD references.

    Parameters
    ----------
    nwbfile : NWBFile
        The file, after the interfaces have added their data and before it is written.
    terms : dict
        The ``ExternalResources`` block: for each kind of value (``species``, ``institution``,
        ``anatomical_structures``), the value as written in the file mapped to its term ``{id, uri}``.
        A value in the file without a term is not annotated.
    """
    herd = HERD()

    def annotate(container, kind, value, attribute=None):
        term = terms.get(kind, {}).get(value)
        if term is not None:
            herd.add_ref(
                container=container, attribute=attribute, key=value, entity_id=term["id"], entity_uri=term["uri"]
            )

    annotate(nwbfile, "institution", nwbfile.institution, attribute="institution")
    annotate(nwbfile.subject, "species", nwbfile.subject.species, attribute="species")

    # Every anatomical `location`: the FiberPhotometryTable column and the virus injections
    for neurodata_object in nwbfile.all_children():
        if isinstance(neurodata_object, DynamicTable) and "location" in neurodata_object.colnames:
            column = neurodata_object["location"]
            for value in dict.fromkeys(column.data):
                annotate(column, "anatomical_structures", value)
        elif isinstance(getattr(neurodata_object, "location", None), str):
            annotate(neurodata_object, "anatomical_structures", neurodata_object.location, attribute="location")

    nwbfile.external_resources = herd
