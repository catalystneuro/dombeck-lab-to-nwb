"""MeaningsTables, with HED annotations, for the categorical columns listed in metadata/value_meanings.yaml."""

from hdmf.common import DynamicTable, MeaningsTable
from ndx_hed import HedLabMetaData, HedTags
from pynwb import NWBFile


def add_value_meanings(nwbfile: NWBFile, annotations: dict) -> None:
    """Write the meanings and HED strings of value_meanings.yaml into the file as MeaningsTables.

    Parameters
    ----------
    nwbfile : NWBFile
        The file, after the interfaces have added their data and before it is written.
    annotations : dict
        The content of ``value_meanings.yaml``: ``hed_schema_version`` and, under ``tables``, for each table
        name and column name, every value of the column mapped to its ``meaning`` and ``hed`` string.
    """
    tables = {
        neurodata_object.name: neurodata_object
        for neurodata_object in nwbfile.all_children()
        if isinstance(neurodata_object, DynamicTable) and not isinstance(neurodata_object, MeaningsTable)
    }
    wrote_meanings = False
    for table_name, columns in annotations["tables"].items():
        if table_name not in tables:
            continue  # the session has no such table (for example a conversion without the processed .mat file)
        table = tables[table_name]
        for column_name, entries in columns.items():
            meanings_table = MeaningsTable(target=table[column_name])
            meanings_table.add_column(
                name="HED",  # the name ndx-hed requires
                description="HED annotation of each value.",
                col_cls=HedTags,
            )
            for value, entry in entries.items():
                meanings_table.add_row(value=value, meaning=entry["meaning"], HED=entry["hed"])
            table.add_meanings_table(meanings_table)
            wrote_meanings = True

    if wrote_meanings:
        # The file records the HED schema version its annotations were validated against
        nwbfile.add_lab_meta_data(HedLabMetaData(hed_schema_version=annotations["hed_schema_version"]))
