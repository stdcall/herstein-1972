#import "bibliography-data.typ": bibliography-data
#import "main-defs.typ": idx, reference-body
#let reset-bib-group(body) = heading(level: 2, numbering: none, body)

// annotation preserves the original compound punctuation, substituting
// {title}, {pages}, etc. from this record and {Key.pages} from a related
// component. userb holds an original journal spelling where shortjournal
// has not been verified; userc names the part associated with a DOI.
#let rich-bib-text(value) = {
  let value = value.replace("'", "’")
  let position = 0
  for match in value.matches(
    regex("_[^_]+_|\\$[A-Za-z](?:_[0-9]+)?\\$|[A-Z][₀₁₂₃₄₅₆₇₈₉]+"),
  ) {
    value.slice(position, match.start)
    let part = match.text
    if part.starts-with("_") {
      emph(part.slice(1, -1))
    } else if part.starts-with("$") {
      eval(part, mode: "markup")
    } else {
      let digits = "₀₁₂₃₄₅₆₇₈₉".clusters()
      let subscript = part
        .slice(1)
        .clusters()
        .map(c => str(digits.position(d => d == c)))
        .join()
      eval("$" + part.first() + "_" + subscript + "$", mode: "markup")
    }
    position = match.end
  }
  value.slice(position)
}
#let bib-group(key) = {
  let entry = bibliography-data.at(key)
  let authors = entry.author.split(" and ")
  let shown = if authors.len() == 1 { authors.first() } else {
    authors.slice(0, -1).join(", ") + ", and " + authors.last()
  }
  if "nameaddon" in entry { shown += ", " + entry.nameaddon }
  reset-bib-group(shown)
}
#let bib-backlinks(target) = context {
  let refs = query(<cross-reference>).filter(it => {
    let value = it.value
    (
      type(value) == dictionary
        and value.at("kind", default: none) == "cross-reference"
        and value.at("target", default: none) == target
        and value.at("bibliographic-mention", default: true)
    )
  })
  let seen = ()
  let pages = ()
  for mention in refs {
    let loc = mention.location()
    if not seen.contains(loc.page()) {
      seen.push(loc.page())
      let position = loc.position()
      let destination = (
        page: position.page,
        x: position.x,
        y: calc.max(0pt, position.y - 8pt),
      )
      let pattern = loc.page-numbering()
      let folio = counter(page).at(loc)
      let shown = if pattern == none { str(folio.first()) } else {
        numbering(pattern, ..folio)
      }
      pages.push(box(context [
        #metadata((
          kind: "page-reference",
          resolved: true,
          target: "bib-mention:" + target,
          position: here().position(),
          target-position: position,
          // Typst adds 10pt above the coordinate destination as well.
          destination-offset-pt: 18,
          description: shown,
        ))
        #link(destination, shown)
      ]))
    }
  }
  if pages.len() > 0 { [ #text(size: 9pt)[\[#pages.join(", ")\]]] }
}
#let background-reading(body) = block(inset: (left: 1em), body)

// Chapter lists show enough information to identify each work. Their
// native references still supply the number, destination and mention.
#let chapter-bibliography(body) = {
  show ref: it => {
    let target = str(it.target)
    if target.starts-with("bib:") {
      let entry = bibliography-data.at(target.slice(4))
      for author in entry.author.split(" and ") {
        idx(author, index: "name")
      }
      let authors = entry.author.replace(
        " and ",
        if entry.at("language", default: none) == "russian" { " и " } else {
          ", "
        },
      )
      let year = entry.at("year", default: "")
      [#rich-bib-text(authors), #emph(rich-bib-text(entry.title))#if (
          year != ""
        ) [ (#year)]. \[#box(reference-body(it, false))\]]
    } else {
      reference-body(it, it.supplement not in (auto, none, [], [°]))
    }
  }
  body
}

#let bib-description(key) = {
  let entry = bibliography-data.at(key)
  if entry.at("translatoraddition", default: "false") == "true" { [\* ] }
  for component in (
    (key,) + entry.at("related", default: "").split(",").filter(k => k != "")
  ) {
    for author in bibliography-data.at(component).author.split(" and ") {
      idx(author, target: label("bib:" + key), index: "name")
    }
  }
  let template = entry
    .annotation
    .split("\"")
    .enumerate()
    .map(pair => {
      let (i, part) = pair
      if i == 0 { part } else {
        (if calc.odd(i) { "“" } else { "”" }) + part
      }
    })
    .join()
  let position = 0
  for match in template.matches(regex("\\{([^{}]+)\\}")) {
    rich-bib-text(template.slice(position, match.start))
    let token = match.captures.first().split(".")
    let data = if token.len() == 1 { entry } else {
      assert(
        token.first() in entry.at("related", default: "").split(","),
        message: "Template references an unrelated bibliography record",
      )
      bibliography-data.at(token.first())
    }
    let field = token.last()
    if field == "journal" {
      emph(rich-bib-text(data.at("shortjournal", default: data.at(
        "userb",
        default: data.at("journal", default: ""),
      ))))
    } else if (
      field == "author" and data.at("language", default: none) == "russian"
    ) {
      rich-bib-text(data.at(field).replace(" and ", " и "))
    } else {
      rich-bib-text(data.at(field))
    }
    position = match.end
  }
  rich-bib-text(template.slice(position))
  for component in (
    (key,) + entry.at("related", default: "").split(",").filter(k => k != "")
  ) {
    let record = bibliography-data.at(component)
    if "doi" in record {
      let part = if "userc" in record { " (" + record.userc + ")" } else { "" }
      [
        #link(
          "https://doi.org/" + record.doi,
          "DOI" + part + ": " + record.doi,
        )]
    }
  }
  bib-backlinks("bib:" + key)
}
