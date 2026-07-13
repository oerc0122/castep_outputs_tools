import pytest
from zipfile import ZipFile
import tarfile
from pathlib import Path

from castep_outputs.tools.md_geom_parser import MDGeomParser
from castep_outputs_tools.md import md_to_force

SELF_DIR = Path(__file__).parent

EXPECTED_OUT = """\
#N 8 1
#C Si
#X  5.4299978328915692E+00  0.0000000000000000E+00  0.0000000000000000E+00
#Y  0.0000000000000000E+00  5.4299978328915692E+00  0.0000000000000000E+00
#Z  0.0000000000000000E+00  0.0000000000000000E+00  5.4299978328915692E+00
#E -1.1184684105164561E+02
#F
0  0.0000000000000000E+00  0.0000000000000000E+00  0.0000000000000000E+00 -2.4370746610307731E-01 -3.2982261041251903E-01  3.2238757014319813E-01
0  0.0000000000000000E+00  2.7149989164457846E+00  2.7964488839391586E+00  3.7856433959149216E-01  3.2200880654817327E-01 -9.8642666612586172E-01
0  2.7149989164457846E+00  0.0000000000000000E+00  2.7692988947747006E+00  3.1293959926591791E-01  3.3938127022917158E-01 -1.1605599506372897E+00
0  2.7149989164457846E+00  2.7149989164457846E+00  0.0000000000000000E+00 -2.6708827113048511E-01 -2.3509386378526215E-01 -2.4109221779826470E-01
0  4.1267983529975938E+00  1.3574994582228923E+00  4.0724983746686778E+00 -8.4881538721340655E-01 -8.8998315097035624E-02  5.5058873014833110E-01
0  1.3031994798939768E+00  1.3574994582228923E+00  1.3574994582228923E+00  5.8397004422095822E-01  5.7348560017552147E-02  5.0559158827294948E-01
0  1.3574994582228923E+00  4.1267983529975938E+00  4.0724983746686778E+00  1.5480579449482854E-01 -5.8607426913899563E-01  5.3941488674919280E-01
0  4.0724983746686778E+00  4.0181983963397618E+00  1.3574994582228923E+00 -7.0668653126227818E-02  5.2125042163891533E-01  4.7009605924774439E-01
"""

@pytest.fixture
def sample_text():
    return (SELF_DIR / "test.md").read_text()

@pytest.fixture
def zip_file(tmp_path, sample_text):
    test_file = tmp_path / "test.zip"
    with ZipFile(test_file, "w") as zipf:
        for tmp in range(3):
            with zipf.open(f"{tmp}.md", "w") as out:
                out.write(bytes(sample_text, encoding="utf-8"))

    yield test_file, 3

@pytest.fixture
def tar_file(tmp_path, sample_text):
    test_file = tmp_path / "test.tar"
    with tarfile.open(test_file, "w") as tarf:
        for tmp in range(3):
            curr = tmp_path / f"{tmp}.md"
            curr.write_text(sample_text)
            tarf.add(curr)

    yield test_file, 3

@pytest.fixture
def raw_dir(tmp_path, sample_text):
    test_dir = tmp_path / "test_dir"
    test_dir.mkdir()
    for tmp in range(3):
        (test_dir / f"{tmp}.md").write_text(sample_text)
    yield test_dir, 3

@pytest.fixture
def raw_file(tmp_path, sample_text):
    test_file = tmp_path / "test.md"
    test_file.write_text(sample_text)
    yield test_file, 1

@pytest.fixture
def files(request, zip_file, tar_file, raw_file, raw_dir):
    sel = {
        "zip": zip_file,
        "tar": tar_file,
        "raw": raw_file,
        "dir": raw_dir,
    }

    return [sel[typ] for typ in request.param]


@pytest.mark.parametrize("path, potential, expected", [
    (SELF_DIR / "test.md", {"Si": 5.}, EXPECTED_OUT),
], ids=["basic"])
def test_md_to_force(path, potential, expected):
    data = MDGeomParser(path)

    result = md_to_force.conf_to_potfit(data[0], potential)

    assert result == expected

@pytest.mark.parametrize("files", [
    ("raw",),
    ("tar",),
    ("zip",),
    ("dir",),
    ("raw", "zip"),
    ("dir", "zip"),
    ("zip", "tar"),
], indirect=True)
def test_get_files(tmp_path, files):
    out_file = tmp_path / "test"
    paths, counts = zip(*files, strict=True)
    md_to_force.main(out_file, paths, {"Si": 5.}, (0,))

    assert out_file.read_text() == EXPECTED_OUT * sum(counts)
