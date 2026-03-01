from dataclasses import dataclass

from app.services.crawl.parsers import BaseParser, IpPortTextParser


@dataclass(frozen=True)
class CrawlSource:
    name: str
    url: str
    parser: BaseParser


DEFAULT_SOURCES: tuple[CrawlSource, ...] = (
    CrawlSource(
        name="proxifly_http",
        url="https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt",
        parser=IpPortTextParser(protocol="http"),
    ),
    CrawlSource(
        name="proxy_list_raw_http",
        url="https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
        parser=IpPortTextParser(protocol="http"),
    ),
)
