"""A PV group that can create and manage local file storage.

Example usage:

.. code-block:: python

    class LocalStorageIOC(PVGroup):
        manager = SubGroup(LocalStorageGroup,
                           prefix="25idc")

"""

import datetime as dt

from aiopath import AsyncPath as Path

from caproto.server import PVGroup, pvproperty
from caproto.server.autosave import autosaved
from pathvalidate import sanitize_filepath


class LocalStorageGroup(PVGroup):
    """A caproto PV group for managing local file storage folders.

    The group will respond to changes in the beamline scheduling
    metadata, and keep track of local file storage to match.

    Assuming the following:
      - the current cycle is 2024-1
      - the PI's for the current proposal are "Wolfman, Kelly"
      - the *base_dir* PV is "/net/s25data/export/25-ID-C/"

    then the *sub_directory* will be "2024-1/Wolfman_Kelly/", and the
    *final_directory* will be
    "/net/s25data/export/25-ID-C/2024-1/Wolfman_Kelly/".

    The intended use is to set the *base_directory* property
    once. Then when the BSS metadata changes, the *sub_directory*
    property will change to reflect the metadata. *final_directory* is
    a combination of both other PVs and can be used to store data.

    """

    file_system = autosaved(pvproperty(
        value="",
        max_length=200,
        string_encoding="utf-8",
        report_as_string=True,
        doc="The static portion of the directory path. Does not change with BSS metadata.",
    ))
    sub_directory = pvproperty(
        value="",
        max_length=200,
        string_encoding="utf-8",
        report_as_string=True,
        doc="The variable portion of the directory path. Based on BSS metadata.",
    )
    full_path = pvproperty(
        value="",
        max_length=400,
        string_encoding="utf-8",
        report_as_string=True,
        read_only=True,
        doc="The combined directory path based on the base and sub directories.",
    )
    exists = pvproperty(
        read_only=True,
        value="Off",
        dtype=bool,
        doc="Whether or not the value of *final_directory* exists on the target filesystem.",
    )
    create = pvproperty(
        dtype=bool,
        doc="Put to this PV to create the *final_directory* on the target filesystem.",
    )

    async def update_PIs(self, PIs):
        """Update the directory structure based on the new PI names provided."""
        # Convert commas and spaces to underscores
        PI_path = PIs.replace(", ", "_").replace(",", "_").replace(" ", "-")
        # Add the current year as a directory
        year = dt.datetime.now().strftime("%Y")
        # Set the current sub_directory PV
        await self.sub_directory.write(f"{year}/{PI_path}")

    async def update_full_path(self, file_system, sub_directory):
        fs = Path(file_system)
        full_path = fs / sub_directory.strip('/')
        # Sanitize the path
        full_path = sanitize_filepath(str(full_path))
        # Write the combined path to the PV
        await self.full_path.write(full_path)

    # Wrap the source PVs so they update the full path
    @file_system.putter
    async def file_system(self, instance, value):
        await self.update_full_path(value, self.sub_directory.value)

    @sub_directory.putter
    async def sub_directory(self, instance, value):
        await self.update_full_path(self.file_system.value, value)

    @full_path.putter
    async def full_path(self, instance, value):
        path = Path(value)
        if await path.exists():
            await self.exists.write(True)
        else:
            await self.exists.write(False)

    @create.putter
    async def create(self, instance, value):
        if value != "On":
            return
        # Create directory
        target = Path(self.full_path.value)
        if not await target.exists():
            await target.mkdir()
        # Update the *exists* PV (check again in case create failed)
        await self.exists.write(await target.exists())
        # Reset the PV
        return "Off"
