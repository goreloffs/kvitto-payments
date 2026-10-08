def test_list_tariffs(client):
    resp = client.get("/tariffs")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    by_code = {t["title"]: t for t in data}
    assert by_code["Basic"]["price"] == 990_000
    assert by_code["Standard"]["price"] == 1_990_000
    assert by_code["Premium"]["price"] == 2_990_000
