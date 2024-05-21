import datetime as dt

import pytest
import time_machine

from caproto.server import PVGroup, SubGroup

from caprotoapps import local_storage


class MockIOC(PVGroup):
    local_storage = SubGroup(local_storage.LocalStorageGroup, prefix="local_storage:")


@pytest.fixture
def test_ioc():
    ioc = MockIOC(prefix="test_ioc:")
    yield ioc


@time_machine.travel(dt.datetime(1985, 10, 26, 1, 24))
@pytest.mark.asyncio
async def test_update_PIs(test_ioc):
    ioc = test_ioc
    await ioc.local_storage.update_PIs("Reynolds, Fry")
    assert ioc.local_storage.sub_directory.value == "1985/Reynolds_Fry"


@pytest.mark.asyncio
async def test_full_path(test_ioc):
    """Does the *full_path* PV get update when the *file_system* and
    *sub_directory* PVs are written.

    """
    pvgrp = test_ioc.local_storage
    # Include some silly '/' to keep things weird
    await pvgrp.file_system.write("/hello/")
    await pvgrp.sub_directory.write("/world")
    assert pvgrp.full_path.value == "/hello/world"


@pytest.mark.asyncio
async def test_sanitize_full_path(test_ioc):
    """Does the *full_path* gracefully handle pathalogical input.

    """
    pvgrp = test_ioc.local_storage
    # Include some silly '/' to keep things weird
    await pvgrp.file_system.write("/he**o/")
    await pvgrp.sub_directory.write("/w:?rl")
    assert pvgrp.full_path.value == "/heo/wrl"


@pytest.mark.asyncio
async def test_exists(test_ioc, tmp_path):
    """Test if the *exists* PV gets updated."""
    pvgrp = test_ioc.local_storage
    scan_dir = tmp_path / "scan_data"
    await pvgrp.file_system.write(str(tmp_path))
    await pvgrp.sub_directory.write("scan_data")
    assert pvgrp.exists.value == "Off"
    # Now create the directory and try again
    scan_dir.mkdir()
    await pvgrp.sub_directory.write("scan_data")
    assert pvgrp.exists.value == "On"


@pytest.mark.asyncio
async def test_create(test_ioc, tmp_path):
    """Test if the *create* PV creates the directory."""
    pvgrp = test_ioc.local_storage
    scan_dir = tmp_path / "scan_data"
    await pvgrp.file_system.write(str(tmp_path))
    await pvgrp.sub_directory.write("scan_data")
    assert pvgrp.exists.value == "Off"
    # Now create the directory using the PV
    await pvgrp.create.write(True)
    # Check that it all came out right
    assert pvgrp.exists.value == "On"
    assert scan_dir.exists()
    
