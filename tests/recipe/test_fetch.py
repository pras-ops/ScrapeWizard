import httpx

from scrapewizard.recipe.fetch import decode_body


def test_meta_charset_is_used_when_the_server_names_none():
    body = '<html><head><meta charset="windows-1252"></head><body>£5 café</body></html>'.encode("windows-1252")
    response = httpx.Response(200, content=body, headers={"content-type": "text/html"})
    assert "£5 café" in decode_body(response)


def test_http_equiv_charset_is_used():
    body = ('<meta http-equiv="content-type" content="text/html; charset=ISO-8859-1">'
            "<p>Preço: 10€</p>").encode("iso-8859-15").replace(b"\xa4", b"E")
    response = httpx.Response(200, content=body, headers={"content-type": "text/html"})
    assert "Preço" in decode_body(response)


def test_header_charset_wins():
    response = httpx.Response(200, content="£5".encode("utf-8"),
                              headers={"content-type": "text/html; charset=utf-8"})
    assert decode_body(response) == "£5"


def test_unknown_declared_charset_falls_back_to_utf8():
    body = '<meta charset="not-a-real-charset"><p>ok</p>'.encode("utf-8")
    response = httpx.Response(200, content=body, headers={"content-type": "text/html"})
    assert "ok" in decode_body(response)
