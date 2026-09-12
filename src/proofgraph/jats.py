from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re
import xml.etree.ElementTree as ET


_EXCLUDED_SUBTREES = {
    "boxed-text",
    "fig",
    "floats-group",
    "media",
    "ref-list",
    "supplementary-material",
    "table-wrap",
}


@dataclass(frozen=True)
class JatsTextElement:
    element_id: str
    xpath: str
    text: str
    text_sha256: str


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def normalize_jats_text(element: ET.Element) -> str:
    """Flatten inline JATS while excluding floating or supplementary content."""

    parts: list[str] = []

    def collect(node: ET.Element) -> None:
        if node.text:
            parts.append(node.text)
        for child in node:
            if _local_name(child.tag) not in _EXCLUDED_SUBTREES:
                collect(child)
            if child.tail:
                parts.append(child.tail)

    collect(element)
    return re.sub(r"\s+", " ", "".join(parts), flags=re.UNICODE).strip()


def _xpath_id(tag: str, element_id: str) -> str:
    if "'" not in element_id:
        return f"{tag}[@id='{element_id}']"
    if '"' not in element_id:
        return f'{tag}[@id="{element_id}"]'
    raise ValueError("JATS element ids containing both quote styles are unsupported")


def _child_segment(parent: ET.Element, child: ET.Element) -> str:
    tag = _local_name(child.tag)
    element_id = (child.get("id") or "").strip()
    if element_id:
        return _xpath_id(tag, element_id)
    same_tag = [node for node in parent if _local_name(node.tag) == tag]
    if len(same_tag) == 1:
        return tag
    return f"{tag}[{same_tag.index(child) + 1}]"


def iter_body_paragraphs(article: ET.Element) -> tuple[JatsTextElement, ...]:
    """Return native-ID body paragraphs with deterministic article-relative paths."""

    body_nodes = [child for child in article if _local_name(child.tag) == "body"]
    if len(body_nodes) != 1:
        return ()
    body = body_nodes[0]
    paragraphs: list[JatsTextElement] = []

    def visit(node: ET.Element, path: str) -> None:
        for child in node:
            tag = _local_name(child.tag)
            if tag in _EXCLUDED_SUBTREES:
                continue
            child_path = f"{path}/{_child_segment(node, child)}"
            if tag == "p":
                element_id = (child.get("id") or "").strip()
                if element_id:
                    text = normalize_jats_text(child)
                    if text:
                        paragraphs.append(
                            JatsTextElement(
                                element_id=element_id,
                                xpath=child_path,
                                text=text,
                                text_sha256=sha256(text.encode("utf-8")).hexdigest(),
                            )
                        )
                continue
            visit(child, child_path)

    visit(body, "article/body")
    return tuple(paragraphs)
