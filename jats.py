"""JATS XML parsing: article metadata, figures, and figure-to-section references."""

from collections import defaultdict
from .utils import local_name, element_text, first_descendant
from .taxonomy import section_category, publication_type_from_article_type


def _all(parent, name):
    return [el for el in parent.iter() if local_name(el.tag) == name] if parent is not None else []


def _first_text(parent, name):
    return element_text(first_descendant(parent, name))


def _pub_year(article_meta):
    for date_el in _all(article_meta, "pub-date"):
        for tag in ("year", "season"):
            value = _first_text(date_el, tag)
            if value and value.isdigit() and len(value) == 4:
                return value
    return ""


def extract_article_metadata(root, pmc_metadata=None):
    pmc_metadata = pmc_metadata or {}
    article = next((x for x in root.iter() if local_name(x.tag) == "article"), root)
    article_meta = first_descendant(article, "article-meta")
    journal_meta = first_descendant(article, "journal-meta")

    journal_title_group = first_descendant(journal_meta, "journal-title-group")
    journal_title = _first_text(journal_title_group, "journal-title")
    if not journal_title:
        journal_title = _first_text(journal_meta, "journal-title")

    issns = []
    for issn in _all(journal_meta, "issn"):
        value = element_text(issn)
        if value:
            issns.append({"value": value, "type": issn.attrib.get("pub-type", "")})

    article_title = _first_text(article_meta, "article-title") or pmc_metadata.get("title", "")
    abstract = _first_text(article_meta, "abstract")
    doi = ""
    pmid = str(pmc_metadata.get("pmid") or "")
    for pub_id in _all(article_meta, "article-id"):
        kind = pub_id.attrib.get("pub-id-type", "").lower()
        value = element_text(pub_id)
        if kind == "doi":
            doi = value
        elif kind in ("pmid", "pubmed"):
            pmid = value

    authors = []
    for contrib in _all(article_meta, "contrib"):
        if contrib.attrib.get("contrib-type", "author") != "author":
            continue
        name = first_descendant(contrib, "name")
        if name is not None:
            given = _first_text(name, "given-names")
            surname = _first_text(name, "surname")
            full = " ".join(x for x in (given, surname) if x)
            if full:
                authors.append(full)

    subjects = [element_text(x) for x in _all(article_meta, "subject") if element_text(x)]
    article_type = article.attrib.get("article-type", "")

    publisher = _first_text(journal_meta, "publisher-name")
    volume = _first_text(article_meta, "volume")
    issue = _first_text(article_meta, "issue")
    year = _pub_year(article_meta) or str(pmc_metadata.get("year") or "")

    return {
        "pmcid": pmc_metadata.get("pmcid", ""),
        "pmid": pmid,
        "doi": doi or pmc_metadata.get("doi", ""),
        "paper_title": article_title,
        "abstract": abstract,
        "journal": journal_title,
        "journal_issns": issns,
        "publisher": publisher,
        "publication_year": year,
        "volume": volume,
        "issue": issue,
        "article_type_raw": article_type,
        "publication_type": publication_type_from_article_type(article_type),
        "article_subjects": subjects,
        "authors": authors,
        "citation": pmc_metadata.get("citation", ""),
        "license_code": pmc_metadata.get("license_code", ""),
        "paper_url": (
            f"https://pmc.ncbi.nlm.nih.gov/articles/{pmc_metadata.get('pmcid', '')}/"
            if pmc_metadata.get("pmcid") else ""
        ),
    }


def _section_title(sec):
    title = first_descendant(sec, "title")
    return element_text(title)


def extract_section_references(root):
    """Return figure IDs and every body section in which they are cited.

    The first substantive body citation is recorded as the primary section.
    A figure may legitimately be referenced in multiple sections.
    """
    body = first_descendant(root, "body")
    if body is None:
        return {}

    parent_map = {child: parent for parent in body.iter() for child in parent}
    section_info = {}

    for sec in _all(body, "sec"):
        title = _section_title(sec)
        path = []
        node = sec
        while node is not None and node is not body:
            if local_name(node.tag) == "sec":
                t = _section_title(node)
                if t:
                    path.append(t)
            node = parent_map.get(node)
        path.reverse()
        section_info[sec] = {
            "section_title": title or "Untitled section",
            "section_path": path,
            "section_category": section_category(title),
        }

    mentions = defaultdict(list)
    order = 0
    for xref in _all(body, "xref"):
        if xref.attrib.get("ref-type", "").lower() not in ("fig", "figure"):
            continue
        rid_values = (xref.attrib.get("rid") or "").split()
        if not rid_values:
            continue

        ancestor = parent_map.get(xref)
        while ancestor is not None and local_name(ancestor.tag) != "sec":
            ancestor = parent_map.get(ancestor)
        if ancestor is None:
            sec_data = {
                "section_title": "Body (unsectioned)",
                "section_path": [],
                "section_category": "unknown",
            }
        else:
            sec_data = section_info.get(ancestor, {
                "section_title": "Unknown section",
                "section_path": [],
                "section_category": "unknown",
            })

        order += 1
        mention = {
            **sec_data,
            "reference_text": element_text(xref),
            "document_order": order,
        }
        for rid in rid_values:
            mentions[rid].append(mention)

    output = {}
    for fig_id, refs in mentions.items():
        unique = []
        seen = set()
        for ref in refs:
            key = (ref["section_title"], tuple(ref["section_path"]))
            if key not in seen:
                seen.add(key)
                unique.append(ref)
        unique.sort(key=lambda x: x["document_order"])
        primary = unique[0] if unique else None
        output[fig_id] = {
            "primary_section": primary["section_category"] if primary else "unknown",
            "primary_section_title": primary["section_title"] if primary else "",
            "all_referenced_sections": unique,
            "section_reference_count": len(refs),
            "section_detection_method": "jats_xref",
        }
    return output


def extract_figures(root, article_metadata, section_refs):
    """Extract one record per JATS figure, retaining all associated image filenames."""
    figures = []
    for fig in _all(root, "fig"):
        fig_id = fig.attrib.get("id", "")
        label = _first_text(fig, "label")
        caption = _first_text(fig, "caption")
        image_filenames = []
        for graphic in fig.iter():
            if local_name(graphic.tag) not in ("graphic", "inline-graphic"):
                continue
            href = ""
            for key, value in graphic.attrib.items():
                if local_name(key) == "href":
                    href = value
                    break
            if href:
                image_filenames.append(href.split("/")[-1])

        figures.append({
            "figure_id": fig_id,
            "figure_label": label,
            "caption": caption,
            "image_filenames": image_filenames,
            "section": section_refs.get(fig_id, {
                "primary_section": "unknown",
                "primary_section_title": "",
                "all_referenced_sections": [],
                "section_reference_count": 0,
                "section_detection_method": "not_referenced_in_body",
            }),
        })
    return figures
