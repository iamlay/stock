from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EtfSeed:
    code: str
    name: str
    category: str
    exchange: str
    tracked_index: str


# Frozen MVP universe (see docs/etf-universe.md). Keep in sync with the doc.
ETF_UNIVERSE: tuple[EtfSeed, ...] = (
    EtfSeed("512890", "中证红利低波ETF", "红利", "SH", "中证红利低波动"),
    EtfSeed("515450", "红利低波50ETF", "红利", "SH", "标普中国A股大盘红利低波50"),
    EtfSeed("515100", "红利低波100ETF", "红利", "SH", "中证红利低波动100"),
    EtfSeed("515080", "中证红利ETF", "红利", "SH", "中证红利"),
    EtfSeed("561580", "央企红利ETF", "红利", "SH", "中证央企红利"),
    EtfSeed("510880", "上证红利ETF", "红利", "SH", "上证红利"),
    EtfSeed("159201", "自由现金流ETF", "现金流", "SZ", "国证自由现金流"),
    EtfSeed("560120", "中证500现金流ETF", "现金流", "SH", "中证500自由现金流"),
    EtfSeed("159941", "纳指100ETF", "跨境", "SZ", "纳斯达克100"),
    EtfSeed("513500", "标普500ETF", "跨境", "SH", "标普500"),
    EtfSeed("513880", "日经225ETF", "跨境", "SH", "日经225"),
    EtfSeed("513050", "中概互联网ETF", "跨境", "SH", "中证海外中国互联网50"),
    EtfSeed("513180", "恒生科技ETF", "跨境", "SH", "恒生科技"),
    EtfSeed("513330", "恒生互联网ETF", "跨境", "SH", "恒生互联网科技业"),
    EtfSeed("510300", "沪深300ETF", "宽基", "SH", "沪深300"),
    EtfSeed("510500", "中证500ETF", "宽基", "SH", "中证500"),
    EtfSeed("512100", "中证1000ETF", "宽基", "SH", "中证1000"),
    EtfSeed("563360", "中证A500ETF", "宽基", "SH", "中证A500"),
    EtfSeed("512480", "半导体ETF", "行业", "SH", "中证全指半导体"),
    EtfSeed("515030", "新能源车ETF", "行业", "SH", "中证新能源汽车"),
)

ETF_BY_CODE = {item.code: item for item in ETF_UNIVERSE}
