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
    element_id: str | None
    xpath: str
    text: str
    text_sha256: str
    ancestor_element_id: str | None = None


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


def body_paragraph_by_section_position(
    article: ET.Element,
    *,
    section_id: str,
    position: int,
) -> JatsTextElement:
    """Select one direct child paragraph under a native-ID body section.

    Some publisher JATS assigns an ID to the containing ``sec`` but not to its
    paragraphs. In that case the exact paragraph can still be addressed by a
    deterministic article-relative XPath rooted at the native section ID. The
    returned ``element_id`` is ``None`` because the selected paragraph has
    no native ID. ``ancestor_element_id`` records the section ID; offsets and
    hashes are for the paragraph selected by ``xpath``.
    """

    if not section_id.strip():
        raise ValueError("section_id must be nonempty")
    if position < 1:
        raise ValueError("paragraph position must be one-based")

    body_nodes = [child for child in article if _local_name(child.tag) == "body"]
    if len(body_nodes) != 1:
        raise ValueError(f"expected exactly one JATS body; found {len(body_nodes)}")
    body = body_nodes[0]
    matches: list[tuple[ET.Element, str]] = []

    def find_sections(node: ET.Element, path: str) -> None:
        for child in node:
            tag = _local_name(child.tag)
            if tag in _EXCLUDED_SUBTREES:
                continue
            child_path = f"{path}/{_child_segment(node, child)}"
            if tag == "sec" and (child.get("id") or "").strip() == section_id:
                matches.append((child, child_path))
            find_sections(child, child_path)

    find_sections(body, "article/body")
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one body section {section_id!r}; found {len(matches)}"
        )
    section, section_path = matches[0]
    paragraphs = [child for child in section if _local_name(child.tag) == "p"]
    if position > len(paragraphs):
        raise ValueError(
            f"section {section_id!r} has {len(paragraphs)} direct paragraph(s); "
            f"cannot select position {position}"
        )
    paragraph = paragraphs[position - 1]
    text = normalize_jats_text(paragraph)
    if not text:
        raise ValueError(
            f"section {section_id!r} paragraph {position} has no supported text"
        )
    return JatsTextElement(
        element_id=None,
        xpath=f"{section_path}/{_child_segment(section, paragraph)}",
        text=text,
        text_sha256=sha256(text.encode("utf-8")).hexdigest(),
        ancestor_element_id=section_id,
    )
