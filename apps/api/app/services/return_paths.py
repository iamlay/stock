"""Only allow passive, same-site product pages as navigation destinations."""
from urllib.parse import parse_qsl, unquote, urlencode, urljoin, urlsplit, urlunsplit

RETURN_ROUTES = {
    "pricing", "account", "dashboard", "watchlist", "etf", "stocks",
    "strategies", "notifications",
}


def safe_return_path(value: str | None) -> str:
    if not isinstance(value, str) or len(value) > 2048:
        return "/account"
    if not value.startswith("/") or value.startswith("//"):
        return "/account"
    if any(ord(char) <= 32 or ord(char) == 127 or char == "\\" for char in value):
        return "/account"
    try:
        url = urlsplit(urljoin("https://stocklab.invalid", value))
        path = url.path
        if url.scheme != "https" or url.netloc != "stocklab.invalid":
            return "/account"
        if not path.isascii() or unquote(path) != path or "%" in path:
            return "/account"
        if path != "/" and path.split("/")[1] not in RETURN_ROUTES:
            return "/account"
        query = url.query
        if path.startswith("/strategies/") and any(
            key == "run" for key, _ in parse_qsl(query, keep_blank_values=True)
        ):
            query = urlencode([(key, value) for key, value in
                               parse_qsl(query, keep_blank_values=True) if key != "run"])
        return urlunsplit(("", "", path, query, url.fragment))
    except ValueError:
        return "/account"
