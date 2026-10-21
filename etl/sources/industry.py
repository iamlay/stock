from __future__ import annotations

import gzip
import json
import time
import urllib.parse
import urllib.request
import zlib
from dataclasses import dataclass

SINA_NODES_API = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodes"
SINA_LIST_API = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
EASTMONEY_F10_API = "https://emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/PageAjax"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"


@dataclass(frozen=True)
class IndustryNode:
    name: str
    code: str


@dataclass(frozen=True)
class CompanyIndustry:
    code: str
    name: str
    eastmoney_industry: str | None
    csrc_industry: str | None
    board: str | None
    listing_date: str | None


def _get_json(url: str, referer: str) -> object:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Referer": referer},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read()
        encoding = response.headers.get("Content-Encoding", "")
    if encoding == "gzip":
        raw = gzip.decompress(raw)
    elif encoding == "deflate":
        raw = zlib.decompress(raw)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("gbk", errors="replace")
    return json.loads(text)


def parse_sina_nodes(payload: object, prefix: str = "new_") -> list[IndustryNode]:
    nodes: list[IndustryNode] = []

    def walk(node: object) -> None:
        if not isinstance(node, list):
            return
        if (
            len(node) >= 3
            and isinstance(node[0], str)
            and isinstance(node[2], str)
            and node[2].startswith(prefix)
        ):
            nodes.append(IndustryNode(name=node[0], code=node[2]))
            return
        for item in node:
            walk(item)

    walk(payload)
    return nodes


def fetch_sina_industry_nodes(prefix: str = "new_") -> list[IndustryNode]:
    payload = _get_json(SINA_NODES_API, "https://finance.sina.com.cn/")
    return parse_sina_nodes(payload, prefix)


def parse_sina_industry_rows(items: list[dict], industry: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for item in items:
        symbol = str(item.get("symbol") or "")
        if not symbol.startswith(("sh", "sz")):
            continue
        code = str(item.get("code") or symbol[2:])
        mapping[code] = industry
    return mapping


def fetch_sina_industry_map(
    *,
    prefix: str = "new_",
    max_nodes: int | None = None,
    page_size: int = 100,
    delay: float = 0.2,
) -> tuple[list[IndustryNode], dict[str, str]]:
    nodes = fetch_sina_industry_nodes(prefix)
    if max_nodes is not None:
        nodes = nodes[:max_nodes]
    mapping: dict[str, str] = {}
    for node in nodes:
        page = 1
        while True:
            query = urllib.parse.urlencode(
                {
                    "node": node.code,
                    "num": page_size,
                    "page": page,
                    "sort": "symbol",
                    "asc": 1,
                }
            )
            items = _get_json(
                f"{SINA_LIST_API}?{query}",
                "https://finance.sina.com.cn/",
            )
            if not items:
                break
            mapping.update(parse_sina_industry_rows(items, node.name))
            page += 1
        time.sleep(delay)
    return nodes, mapping


def parse_eastmoney_company(payload: dict, code: str) -> CompanyIndustry:
    basic = (payload.get("jbzl") or [{}])[0]
    listing = (payload.get("fxxg") or [{}])[0]
    return CompanyIndustry(
        code=code,
        name=str(basic.get("SECURITY_NAME_ABBR") or ""),
        eastmoney_industry=basic.get("EM2016"),
        csrc_industry=basic.get("INDUSTRYCSRC1"),
        board=basic.get("SECURITY_TYPE"),
        listing_date=str(listing.get("LISTING_DATE") or "")[:10] or None,
    )


def fetch_eastmoney_industry(code: str) -> CompanyIndustry:
    prefix = "SH" if code.startswith(("5", "6", "9")) else "SZ"
    payload = _get_json(
        f"{EASTMONEY_F10_API}?code={prefix}{code}",
        "https://quote.eastmoney.com/",
    )
    return parse_eastmoney_company(payload, code)
