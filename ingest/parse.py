"""Parse cached wikitext into typed entities and text chunks.

Entity type comes from the infobox template name ({{Character}}, {{Planet}}...).
Continuity comes from the /Legends title suffix or the Legends category.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import mwparserfromhell as mw
from mwparserfromhell.wikicode import Wikicode

_NON_INFOBOX = {
    "top",
    "otheruses",
    "youmay",
    "multipleissues",
    "quote",
    "dialogue",
    "redirect",
    "about",
    "correct title",
    "shortstory",
    "update",
    "more",
    "expand",
    "image",
    "citation",
    "cite",
    "eras",
    "title",
    "conjecture",
    "disambig",
    "nocanon",
    "noncanon",
    "interlang",
    "cn",
    "storycite",
    "legoweb",
}

_SKIP_PARAMS = {
    "image",
    "image2",
    "image3",
    "imagesize",
    "caption",
    "option1",
    "option2",
    "option3",
    "name",
    "hide",
}

_SKIP_SECTIONS = {
    "appearances",
    "sources",
    "notes and references",
    "external links",
    "non-canon appearances",
    "real-world similarities",
    "bibliography",
}

_CHUNK_MAX = 1500


@dataclass
class Entity:
    title: str
    name: str
    type: str
    continuity: str  # "canon" | "legends"
    fields: dict[str, dict] = field(default_factory=dict)  # param -> {text, links}
    chunks: list[dict] = field(default_factory=list)  # {section, text}


def _clean(code: Wikicode) -> str:
    """Wikicode -> plain text: drop refs, templates, files; keep link labels."""
    code = mw.parse(str(code))  # work on a copy
    for tag in code.filter_tags(recursive=True):
        if tag.tag in ("ref", "gallery", "table"):
            try:
                code.remove(tag)
            except ValueError:
                pass
    for tpl in code.filter_templates(recursive=True):
        try:
            code.remove(tpl)
        except ValueError:
            pass
    for link in code.filter_wikilinks(recursive=True):
        if str(link.title).lower().startswith(("file:", "image:", "category:")):
            try:
                code.remove(link)
            except ValueError:
                pass
    text = code.strip_code(normalize=True, collapse=True)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _links(code: Wikicode) -> list[str]:
    out = []
    for link in code.filter_wikilinks(recursive=True):
        target = str(link.title).split("#")[0].strip()
        if target and not target.lower().startswith(("file:", "image:", "category:")):
            out.append(target[0].upper() + target[1:] if target[0].islower() else target)
    return list(dict.fromkeys(out))  # dedupe, keep order


def _top_flags(code: Wikicode) -> set[str]:
    """Positional flags of the {{Top}} status template (real, rwp, rwm, leg...)."""
    for tpl in code.filter_templates(recursive=False):
        if str(tpl.name).strip().lower() == "top":
            return {
                str(p.value).strip().lower() for p in tpl.params if str(p.name).strip().isdigit()
            }
    return set()


def _is_real_world(flags: set[str]) -> bool:
    return any(f == "real" or f.startswith("rw") for f in flags)


class PageParser:
    """Turns one cached wiki page into an Entity (or nothing)."""

    # Templates that look like infoboxes (many named params) but aren't.
    NON_INFOBOX = _NON_INFOBOX
    # Infobox params that are page furniture, never lore.
    SKIP_PARAMS = _SKIP_PARAMS
    SKIP_SECTIONS = _SKIP_SECTIONS
    CHUNK_MAX = _CHUNK_MAX

    def parse(self, title: str, wikitext: str, categories: list[str]) -> Entity | None:
        """Returns None for real-world pages (actors, films, companies) and redirects.

        In-universe pages without an infobox (concepts like Lightsaber, Blaster)
        become type "Topic": no relations, but their text still gets chunked.
        """
        code = mw.parse(wikitext)
        if _is_real_world(_top_flags(code)):
            return None
        infobox = self._find_infobox(code)
        if infobox is None and not code.filter_headings():
            return None  # redirect or stub, nothing to index

        continuity = (
            "legends"
            if title.endswith("/Legends") or "Category:Legends articles" in categories
            else "canon"
        )
        entity = Entity(
            title=title,
            name=title.removesuffix("/Legends"),
            type="Topic"
            if infobox is None
            else "".join(
                w.capitalize() for w in re.split(r"[^A-Za-z0-9]+", str(infobox.name)) if w
            ),
            continuity=continuity,
        )

        for param in infobox.params if infobox is not None else []:
            pname = str(param.name).strip().lower()
            if pname in self.SKIP_PARAMS or pname.isdigit():
                continue
            text = _clean(param.value)
            links = _links(param.value)
            if text or links:
                entity.fields[pname] = {"text": text, "links": links}

        for i, section in enumerate(code.get_sections(levels=[2], include_lead=True)):
            headings = section.filter_headings()
            heading = _clean(headings[0].title) if headings else "Introduction"
            if heading.lower() in self.SKIP_SECTIONS:
                continue
            if i == 0:  # lead: infobox already consumed, drop it from the text
                section = mw.parse(str(section))
            text = _clean(section)
            if headings:
                text = text.removeprefix(heading).strip()
            if len(text) < 40:
                continue
            for part in self._split_paragraphs(text):
                entity.chunks.append({"section": heading, "text": part})

        return entity

    def _find_infobox(self, code: Wikicode):
        # Infoboxes only ever live in the lead — searching further finds
        # footer templates like {{Interlang}} instead.
        lead = code.get_sections(levels=[2], include_lead=True)[0]
        for tpl in lead.filter_templates(recursive=False):
            name = str(tpl.name).strip().lower()
            named = [p for p in tpl.params if not str(p.name).strip().isdigit()]
            if name not in self.NON_INFOBOX and len(named) >= 3:
                return tpl
        return None

    def _split_paragraphs(self, text: str) -> list[str]:
        if len(text) <= self.CHUNK_MAX:
            return [text]
        parts, cur = [], ""
        for para in text.split("\n\n"):
            if cur and len(cur) + len(para) > self.CHUNK_MAX:
                parts.append(cur.strip())
                cur = ""
            cur += para + "\n\n"
        if cur.strip():
            parts.append(cur.strip())
        return parts
