import pytest

from nezka_invoice.db import ClientRepository, connect
from nezka_invoice.models import Client
from nezka_invoice.quickbooks_import import ImportFileError, import_clients, preview_file, row_to_client

DESKTOP_CSV = (
    ",Active Status,Customer,Balance,Company,First Name,Last Name,Main Phone,Alt. Phone,Main Email,"
    "Bill to 1,Bill to 2,Bill to 3,Bill to 4,Resale Num\r\n"
    ",Active,Tree Logistics,0.00,A Tree Corporation Branch,Ana,Pérez,305-555-0101,305-555-0199,"
    "ops@tree.com; billing@tree.com,A Tree Corporation Branch,7200 NW 25th St,\"Miami, FL 33122\",USA,12-3456789\r\n"
    ",Active,Tree Logistics:Warehouse 2,0.00,,,,,,,,,,,\r\n"
    ",Inactive,Bodega Latina,0.00,,,,786-555-0000,,no-es-correo,,,,,\r\n"
)

IIF = (
    "!HDR\tPROD\tVER\r\n"
    "HDR\tQuickBooks Pro\tVersion 33.0\r\n"
    "!CUST\tNAME\tBADDR1\tBADDR2\tBADDR3\tPHONE1\tEMAIL\tCONT1\tCOMPANYNAME\tHIDDEN\r\n"
    "CUST\tSedano's\t\"3140 W 76th St\"\tHialeah, FL 33018\t\t305-555-2222\tcompras@sedanos.com\tLuis\tSedano's Supermarkets\tN\r\n"
    "CUST\tOld Client\t\t\t\t\t\t\t\tY\r\n"
)

ONLINE_CSV = (
    "Customer,Company name,Street Address,City,State,Country,Zip,Phone,Email,Open Balance,Notes\n"
    "Presidente Supermarket,Presidente Supermarket,1200 W 49th St,Hialeah,FL,USA,33012,305-555-3333,"
    "ap@presidente.com,100.00,Paga a 30 días\n"
)


@pytest.fixture
def repo():
    conn = connect(":memory:", seed=False)
    yield ClientRepository(conn)
    conn.close()


def write(tmp_path, name, content, encoding="utf-8"):
    path = tmp_path / name
    path.write_bytes(content.encode(encoding))
    return path


def test_desktop_csv_with_title_rows_and_cp1252(tmp_path):
    path = write(tmp_path, "customers.csv", "Elpidio Jr\r\nCustomer Contact List\r\n\r\n" + DESKTOP_CSV, "cp1252")
    preview = preview_file(path)
    assert preview.jobs_skipped == 1
    assert [r.client.name for r in preview.rows] == ["Tree Logistics", "Bodega Latina"]

    tree = preview.rows[0].client
    assert tree.branch == "A Tree Corporation Branch"
    assert tree.contact_name == "Ana Pérez"
    assert tree.email == "ops@tree.com"
    assert tree.phone == "305-555-0101"
    assert tree.mobile == "305-555-0199"
    assert tree.address == "7200 NW 25th St"
    assert (tree.city, tree.state, tree.zip_code, tree.country) == ("Miami", "FL", "33122", "USA")
    assert tree.tax_id == "12-3456789"
    assert "billing@tree.com" in tree.notes
    assert tree.active

    bodega = preview.rows[1].client
    assert not bodega.active
    assert bodega.email == ""
    assert "no-es-correo" in bodega.notes


def test_iif_customer_list(tmp_path):
    preview = preview_file(write(tmp_path, "lists.iif", IIF))
    sedanos, old = (r.client for r in preview.rows)
    assert sedanos.name == "Sedano's"
    assert sedanos.branch == "Sedano's Supermarkets"
    assert sedanos.contact_name == "Luis"
    assert (sedanos.address, sedanos.city, sedanos.zip_code) == ("3140 W 76th St", "Hialeah", "33018")
    assert sedanos.active and not old.active


def test_online_csv_with_separate_address_columns(tmp_path):
    client = preview_file(write(tmp_path, "online.csv", ONLINE_CSV)).rows[0].client
    assert client.branch == ""
    assert (client.address, client.city, client.state, client.zip_code) == ("1200 W 49th St", "Hialeah", "FL", "33012")
    assert client.notes == "Paga a 30 días"


def test_xlsx(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["Customer", "Main Phone", "Main Email"])
    sheet.append(["Tree Logistics", "305-555-0101", "ops@tree.com"])
    sheet.append([None, None, None])
    path = tmp_path / "customers.xlsx"
    workbook.save(path)
    rows = preview_file(path).rows
    assert len(rows) == 1
    assert rows[0].client.email == "ops@tree.com"


def test_duplicates_are_skipped_and_import_saves_only_new(tmp_path, repo):
    repo.add(Client(name="tree logistics"))
    content = DESKTOP_CSV + ",Active,Bodega Latina,0.00,,,,,,,,,,,\r\n"
    preview = preview_file(write(tmp_path, "c.csv", content), {c.name for c in repo.list()})
    assert [(r.client.name, r.skip_reason) for r in preview.rows] == [
        ("Tree Logistics", "Ya existe"),
        ("Bodega Latina", ""),
        ("Bodega Latina", "Repetido en el archivo"),
    ]
    saved = import_clients(repo, preview)
    assert [c.name for c in saved] == ["Bodega Latina"]
    assert len(repo.list()) == 2


def test_file_without_customer_column(tmp_path):
    with pytest.raises(ImportFileError):
        preview_file(write(tmp_path, "x.csv", "Item,Price\nApple,1\n"))


def test_desktop_xlsm_with_tips_sheet(tmp_path):
    """Layout of a real QuickBooks Desktop "Export Customer List" workbook."""
    openpyxl = pytest.importorskip("openpyxl")
    workbook = openpyxl.Workbook()
    workbook.active.title = "QuickBooks Desktop Export Tips"
    workbook.active.append([None, "Tips"])
    sheet = workbook.create_sheet("Sheet1")
    sheet.append([None, "Customer", "Balance Total", "Company", "First Name", "Last Name", "Primary Contact",
                  "Main Phone", "Fax", "Main Email"])
    sheet.append([None, "ADOLFO  AND  SON  PRODUCE", 0, "ADOLFO  AND  SON  PRODUCE", None, None, None, None, None, None])
    sheet.append([None, "TOTAL GREEN TROPICALS,INC.", 0, "TOTAL GREEN TROPICALS,INC.", None, None, None,
                  "786-332-3850", "305-635-2350", "management@totalgreentropicals.com"])
    sheet.append([None, "FREEDOM FRESH", 0, "FREEDOM FRESH", "Ana", "Ruiz", "Luis", None, None, "www.freedomfresh.com"])
    path = tmp_path / "quickbook customer.xlsm"
    workbook.save(path)

    adolfo, total_green, freedom = (r.client for r in preview_file(path).rows)
    assert adolfo.name == "ADOLFO AND SON PRODUCE"
    assert adolfo.branch == ""
    assert total_green.name == "TOTAL GREEN TROPICALS,INC."
    assert total_green.phone == "786-332-3850"
    assert total_green.notes == "Fax: 305-635-2350"
    assert freedom.contact_name == "Luis"
    assert freedom.email == ""
    assert freedom.notes == "Sitio web: www.freedomfresh.com"


@pytest.mark.parametrize(
    "lines, expected",
    [
        (["AAA PRODUCE LLC.", "Osmani Musuli", "1233 NW 21 st", "Miami FL 31442"], ("1233 NW 21 st", "Miami", "FL", "31442", "")),
        (["ADOLFO AND SON", "2100 NW 13 AVE.", "MIAMI., FL. 33142", "U.S.A.`"], ("2100 NW 13 AVE.", "Miami", "FL", "33142", "USA")),
        (["X", "4000 Ponce de Leon Boulevard", "Suit #470", "Coral Gables,FL 33146"],
         ("4000 Ponce de Leon Boulevard, Suit #470", "Coral Gables", "FL", "33146", "")),
        (["X", "2101 NW 15 AVE MIAMI, FL 33142"], ("2101 NW 15 AVE", "Miami", "FL", "33142", "")),
        (["X", "500 NE 185 ST MIAMI FLA,", "33179"], ("500 NE 185 ST", "Miami", "FL", "33179", "")),
        (["X", "7630 MIRAMAR PARK WAY", "MIRAMAR,FL.33023"], ("7630 MIRAMAR PARK WAY", "Miramar", "FL", "33023", "")),
        (["X", "2151 NW 13 AVE", "MIAMI,FL 33142", "BAY 23"], ("2151 NW 13 AVE, BAY 23", "Miami", "FL", "33142", "")),
        (["X", "11501NW 107 TH STREET", "MIAMI, FL33178", "FL 33178", "USA"], ("11501NW 107 TH STREET", "Miami", "FL", "33178", "USA")),
        (["X", "201 MONTEREY - SALINAS HWY", "SALINAS, CA 93908"], ("201 MONTEREY - SALINAS HWY", "Salinas", "CA", "93908", "")),
    ],
)
def test_hand_typed_bill_to_lines(lines, expected):
    values = {"name": lines[0], "first_name": "Osmani", "last_name": "Musuli"}
    values.update({f"line{i}": line for i, line in enumerate(lines, start=1)})
    client = row_to_client(values)
    assert (client.address, client.city, client.state, client.zip_code, client.country) == expected


def test_terms_secondary_contact_and_ship_to_go_to_notes():
    client = row_to_client({
        "name": "ALWAYS FRESH", "terms": "Net 21", "secondary_contact": "Jorge",
        "ship1": "ALWAYS FRESH", "ship2": "2101 NW 15 AVE", "ship3": "MIAMI, FL 33142",
    })
    assert client.notes.splitlines() == [
        "Otro contacto: Jorge", "Términos de pago: Net 21", "Enviar a: 2101 NW 15 AVE, MIAMI, FL 33142",
    ]
    assert row_to_client({"name": "X", "ship1": "SAME"}).notes == ""
