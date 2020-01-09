# -*- coding: utf-8 -*-
# Author: Dirk Eilander (contact: dirk.eilander@deltares.nl)
# August 2019

"""Tests for the pyflwdir.core_xxx.py and pyflwdir.core.py submodules."""

import pytest
import numpy as np

from pyflwdir import (
    core, core_d8, core_nextxy, core_ldd
)
from pyflwdir.core_conversion import ldd_to_d8, d8_to_ldd
from pyflwdir.core import _mv

# read and parse data
@pytest.fixture
def _d8():
    return np.fromfile(r'./tests/data/d8.bin', dtype=np.uint8).reshape((678, 776))
@pytest.fixture
def d8_parsed(_d8):
    return core_d8.from_flwdir(_d8)
@pytest.fixture
def ldd_parsed():
    _ldd = np.fromfile(r'./tests/data/ldd.bin', dtype=np.uint8).reshape((678, 776))
    return core_ldd.from_flwdir(_ldd)
@pytest.fixture
def nextxy_parsed():
    _nextxy = np.fromfile(r'./tests/data/nextxy.bin', dtype=np.int32).reshape((2, 678, 776))
    return core_nextxy.from_flwdir(_nextxy)


def test_core_xxx_simple():
    """test core_xxx.py submodules based on _us and _ds definitions"""
    for fd in [core_nextxy, core_d8, core_ldd]:
        _invalid = np.array([[2,4,8],[10,0,-1]], dtype=np.uint8)
        _shape = fd._us.shape
        if fd._ftype == 'nextxy':
            _invalid = np.stack([_invalid, _invalid])
            _shape = fd._us.shape[1:]
        # test isvalid
        assert fd.isvalid(fd._us), "isvalid test with _us data failed"
        assert not fd.isvalid(_invalid), "isvalid false test with invalid data failed"
        # test ispit
        assert np.all(fd.ispit(fd._pv)), "ispit test with _pv data failed"
        # test isnodata 
        assert np.all(fd.isnodata(fd._mv)), "isnodata test with _mv data failed"
        # test data type / dim errors
        with pytest.raises(TypeError):
            fd.from_flwdir(fd._us[None, ...])
            fd.from_flwdir(fd._us.astype(np.float))
        # test upstream / downstream / pit with _us data
        idxs_valid, idxs_ds, idxs_us, idx_pits = fd.from_flwdir(fd._us)
        assert np.all(idxs_valid == np.arange(9)), "valid idx test with _us data failed"
        assert np.all(idxs_ds == 4), "downstream idx test with _us data failed"
        assert (np.all(idx_pits == 4) and 
                idx_pits.size == 1), "pit idx test with _us data failed"
        assert (np.all(idxs_us[4,:]==np.array([0, 1, 2, 3, 5, 6, 7, 8])) and
                np.all(idxs_us[:4, :]==_mv) and 
                np.all(idxs_us[5:, :]==_mv)), "upstream idx test with _us data failed"
        assert np.all(fd.to_flwdir(idxs_valid, idxs_ds, _shape) == fd._us), "convert back with _us data failed"
        # test all invalid/pit with _ds data
        idxs_valid, idxs_ds, idxs_us, idx_pits = fd.from_flwdir(fd._ds)
        assert (np.all(idxs_valid == idx_pits) and 
                np.all(idxs_us == _mv)), "test all pits with _ds data failed"

def test_core_xxx_realdata(d8_parsed, ldd_parsed, nextxy_parsed):
    """test core_xxx.py submodules with actual flwdir data"""
    _d8_ = d8_parsed
    fdict = dict(
        ldd = ldd_parsed, nextxy = nextxy_parsed
    )
    # test conistent results
    for ftype, _fd_ in fdict.items():
        for i in range(len(_d8_)):
            assert np.all(_d8_[i] == _fd_[i]), f"disagreement between 'd8' and '{ftype}'' output {i}"
    
def test_core_d8():
    """test d8_upstream and d8_upstream functions"""
    fd = core_d8
    _us_flat = fd._us.flatten()
    _ds_flat = fd._ds.flatten()
    shape = fd._us.shape
    # test upstream
    for idx0 in range(9):
        flwdir_flat = np.zeros(9, dtype=np.uint8)
        flwdir_flat[idx0] = np.uint8(1)
        flwdir_flat *= _us_flat
        if idx0 != 4:
            assert np.all(fd.upstream(4, flwdir_flat, shape) == idx0), 'd8_upstream failed'
        else:
            assert fd.upstream(4, flwdir_flat, shape).size == 0, 'd8_upstream failed'
    # test downstream
    for idx0 in range(9):
        if idx0 != 4:
            assert fd.downstream(idx0, _ds_flat, shape) == -1, 'd8_downstream failed'
        else:
            assert fd.downstream(idx0, _ds_flat, shape) == 4, 'd8_downstream failed'
        assert fd.downstream(idx0, _us_flat, shape, dd= _us_flat[idx0]) == 4, 'd8_downstream failed'
        assert fd.downstream(idx0, _us_flat, shape) == 4, 'd8_downstream failed'
    # test idx_to_dd
    for idx0 in range(9):
        assert fd.idx_to_dd(idx0, 4, (3,3)) == _us_flat[idx0]

def test_ftype_conversion():
    """test conversion between d8 and ldd formats"""
    assert np.all(d8_to_ldd(ldd_to_d8(core_ldd._ds)) == core_ldd._ds), 'conversion of ldd failed'
    assert np.all(ldd_to_d8(d8_to_ldd(core_d8._ds)) == core_d8._ds), 'conversion of d8 failed'

def test_core_realdata(_d8, d8_parsed):
    """test core.py submodule with actual flwdir data"""
    # test parsing real data
    idxs_valid, idxs_ds, idxs_us, idxs_pit = d8_parsed
    assert idxs_us[idxs_us!=_mv].size + idxs_pit.size == idxs_ds.size
    # test network tree
    try:
        tree = core.network_tree(idxs_pit, idxs_us)
    except:
        pytest.fail('tree network failed')
    assert np.array([leave.size for leave in tree]).sum() == idxs_ds.size, 'tree network invalid'
    # test internal data reshaping / reindexing functions
    assert np.all(core._internal_idx(idxs_valid, idxs_valid, _d8.size) == np.arange(idxs_valid.size))
    assert np.all(core._reshape(_d8.flat[idxs_valid], idxs_valid, _d8.shape, nodata = core_d8._mv) == _d8)
    with pytest.raises(ValueError):
        core._reshape(_d8.flat[idxs_valid[:-1]], idxs_valid, _d8.shape, nodata = core_d8._mv)
    # test upstream functions
    for idx0 in [idxs_pit[0], idxs_pit]:
        assert np.all(core.upstream(idx0, idxs_us) == idxs_us[idx0,:][idxs_us[idx0,:]!=_mv])
    try:
        idxs = np.arange(idxs_ds.size, dtype=np.uint32)
        idxs_us_main = core.main_upstream(idxs, idxs_us, np.ones(idxs.size))
    except:
        pytest.fail('main upstream index failed')
    assert np.all(idxs_us_main == idxs_us[:,0]), 'main upstream index failed'
    # test downstream_river with only stream cell at pit
    river_flat = np.zeros(idxs_ds.size, dtype=np.bool)
    river_flat[idxs_pit] = True
    idxs_ds_stream = core.downstream_river(np.arange(3, dtype=np.uint32), idxs_ds, river_flat)
    assert np.all(idxs_ds_stream == idxs_pit), 'downstream stream index failed'
    # test pit / loop indices
    assert np.all(core.pit_indices(idxs_ds) == idxs_pit), 'pit index failed'
    assert core.loop_indices(idxs_ds, idxs_us).size == 0, 'loop index failed'
    # test2 loop indices remove pit and check all cells are invalid
    idxs_ds_loop = idxs_ds.copy()
    idxs_ds_loop[idxs_pit] = idxs_valid[0]
    assert core.loop_indices(idxs_ds_loop, idxs_us).size == idxs_ds.size, 'loop index invalid'