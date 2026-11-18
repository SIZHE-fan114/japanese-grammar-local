"""Split the authored Japanese introduction into its existing reading pages."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from html import escape
from html.parser import HTMLParser


VOID_TAGS = frozenset(
    ("area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr")
)
_HEADINGS = frozenset(("h3", "h4"))
_LISTS = frozenset(("ol", "ul"))
_COMPANION_CLASSES = frozenset(("jp-ex", "jp-bad-ex", "jp-tip"))
_FALLBACK_HTML = "<p>请阅读本节语法说明并继续。</p>"


@dataclass
class HtmlNode:
    tag: str
    attrs: tuple[tuple[str, str | None], ...] = ()
    children: list[HtmlNode | str] = field(default_factory=list)

    @property
    def elements(self) -> list[HtmlNode]:
        return [node for node in self.children if isinstance(node, HtmlNode)]

    @property
    def classes(self) -> frozenset[str]:
        return frozenset((dict(self.attrs).get("class") or "").split())

    def html(self) -> str:
        inner = nodes_html(self.children)
        if not self.tag:
            return inner
        attrs = "".join(f' {name}="{escape(value or "", quote=True)}"' for name, value in self.attrs)
        start = f"<{self.tag}{attrs}>"
        return start if self.tag in VOID_TAGS else f"{start}{inner}</{self.tag}>"

    def raw_text(self) -> str:
        return "".join(node if isinstance(node, str) else node.raw_text() for node in self.children)

    def text(self) -> str:
        return " ".join(self.raw_text().split())


def nodes_html(nodes: Sequence[HtmlNode | str]) -> str:
    return "".join(
        escape(node, quote=False).replace("\xa0", "&nbsp;") if isinstance(node, str) else node.html()
        for node in nodes
    )


class _FragmentParser(HTMLParser):
    def __init__(self, validate_node: Callable[[HtmlNode], None] | None):
        super().__init__(convert_charrefs=True)
        self.root = HtmlNode("")
        self.stack = [self.root]
        self.validate_node = validate_node

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = HtmlNode(tag, tuple(attrs))
        if self.validate_node:
            self.validate_node(node)
        self.stack[-1].children.append(node)
        if tag not in VOID_TAGS:
            if len(self.stack) >= 48:
                raise ValueError("Excessive markup nesting")
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if len(self.stack) <= 1 or self.stack[-1].tag != tag:
            raise ValueError("Mismatched closing tag")
        self.stack.pop()

    def handle_data(self, data: str) -> None:
        children = self.stack[-1].children
        if children and isinstance(children[-1], str):
            children[-1] += data
        else:
            children.append(data)

    def _unsupported_markup(self, _value: str) -> None:
        if self.validate_node:
            raise ValueError("Unsupported markup")

    handle_decl = _unsupported_markup
    unknown_decl = _unsupported_markup
    handle_pi = _unsupported_markup
    handle_comment = _unsupported_markup


def parse_fragment(raw: str, validate_node: Callable[[HtmlNode], None] | None = None) -> HtmlNode:
    parser = _FragmentParser(validate_node)
    try:
        parser.feed(raw)
        parser.close()
    except AssertionError as error:
        # HTMLParser raises AssertionError for malformed marked declarations.
        raise ValueError("Invalid markup declaration") from error
    if len(parser.stack) != 1:
        raise ValueError("Unclosed markup")
    return parser.root


def _js_length(value: str) -> int:
    # The browser's original page splitter measures UTF-16 code units.
    return len(value.encode("utf-16-le")) // 2


def _length(nodes: list[HtmlNode]) -> int:
    return sum(_js_length(node.text()) for node in nodes)


def _list_groups(nodes: list[HtmlNode], list_node: HtmlNode, title: str) -> list[list[HtmlNode]]:
    items = [node for node in list_node.elements if node.tag == "li"]
    total_length = _length(items)
    if len(items) <= 2 or (len(items) <= 3 and total_length < 420):
        return []
    position = nodes.index(list_node)
    size = 2 if len(items) >= 5 or total_length > 750 else (len(items) + 1) // 2
    groups = []
    for index in range(0, len(items), size):
        lead = nodes[:position] if index == 0 and position else [HtmlNode("h4", children=[title])]
        groups.append([*lead, HtmlNode(list_node.tag, list_node.attrs, list(items[index:index + size]))])
    groups[-1].extend(nodes[position + 1:])
    return groups


def _groups(nodes: list[HtmlNode], title: str) -> list[list[HtmlNode]]:
    lists = [node for node in nodes if node.tag in _LISTS]
    if len(lists) == 1 and nodes.index(lists[0]) >= len(nodes) - 2:
        groups = _list_groups(nodes, lists[0], title)
        if groups:
            return groups
    if len(nodes) <= 2 or _length(nodes) <= 680:
        return [nodes]

    groups = []
    bucket: list[HtmlNode] = []
    bucket_length = 0
    for node in nodes:
        keep_with_heading = len(bucket) == 1 and bucket[0].tag in _HEADINGS
        if bucket_length >= 460 and not keep_with_heading and not node.classes & _COMPANION_CLASSES:
            groups.append(bucket)
            bucket = []
            bucket_length = 0
        bucket.append(node)
        bucket_length += _js_length(node.text())
    if groups and bucket_length < 120:
        groups[-1].extend(bucket)
    else:
        groups.append(bucket)

    for index, group in enumerate(groups):
        if index and group[0].tag not in _HEADINGS:
            group.insert(0, HtmlNode("h4", children=[title]))
    return groups


def split_introduction_steps(html: str, fallback_title: str = "语法核心讲解") -> list[dict[str, str]]:
    """Derive stable page boundaries from source HTML before applying edits."""
    raw = html.strip() or _FALLBACK_HTML
    try:
        fragment = parse_fragment(raw)
    except ValueError:
        return [{"title": fallback_title, "html": raw, "text": ""}]
    if not fragment.elements:
        return [{"title": fallback_title, "html": raw, "text": fragment.text()}]

    sections: list[tuple[str, list[HtmlNode]]] = []
    for node in fragment.elements:
        if not sections or node.tag in _HEADINGS:
            sections.append((node.text() if node.tag in _HEADINGS else "", []))
        sections[-1][1].append(node)
    if len(sections) > 1 and not sections[0][0]:
        _, lead = sections[0]
        if _js_length(" ".join(node.text() for node in lead).strip()) < 90:
            sections[1][1][0:0] = lead
            sections.pop(0)
        else:
            sections[0] = (f"{fallback_title} · 导读", lead)

    pages = []
    for title, section in sections:
        title = title or fallback_title
        groups = _groups(section, title)
        for index, group in enumerate(groups):
            pages.append({
                "title": f"{title}（{index + 1}/{len(groups)}）" if len(groups) > 1 else title,
                "html": nodes_html(group),
                "text": HtmlNode("", children=list(group)).text(),
            })
    return pages
