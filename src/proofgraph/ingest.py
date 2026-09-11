from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path


@dataclass(frozen=True)
class SourceElement:
    element_id: str
    tag: str
    text: str


@dataclass(frozen=True)
class IngestedDocument:
    path: Path
    sha256: str
    title: str
    license: str
    elements: tuple[SourceElement, ...]


class _EvidenceHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._capture: dict[str, object] | None = None
        self.elements: list[SourceElement] = []
        self.title_parts: list[str] = []
        self.in_title = False
        self.license = "unknown"

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "title":
            self.in_title = True
        if tag == "meta" and attributes.get("name") == "license":
            self.license = attributes.get("content") or "unknown"
        element_id = attributes.get("id")
        if element_id:
            self._capture = {"element_id": element_id, "tag": tag, "parts": []}

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        if self._capture and self._capture["tag"] == tag:
            parts = self._capture["parts"]
            assert isinstance(parts, list)
            text = " ".join("".join(parts).split())
            if text:
                self.elements.append(
                    SourceElement(
                        element_id=str(self._capture["element_id"]),
                        tag=str(self._capture["tag"]),
                        text=text,
                    )
                )
            self._capture = None

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)
        if self._capture:
            parts = self._capture["parts"]
            assert isinstance(parts, list)
            parts.append(data)


def ingest_html(path: str | Path) -> IngestedDocument:
    source_path = Path(path).resolve()
    raw = source_path.read_bytes()
    parser = _EvidenceHTMLParser()
    parser.feed(raw.decode("utf-8"))
    title = " ".join("".join(parser.title_parts).split()) or source_path.stem
    return IngestedDocument(
        path=source_path,
        sha256=sha256(raw).hexdigest(),
        title=title,
        license=parser.license,
        elements=tuple(parser.elements),
    )
