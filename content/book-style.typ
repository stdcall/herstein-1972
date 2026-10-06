// Page design, running heads, headings and shared typography.

#import "numbering.typ": place-key, restart-counters
#import "statements.typ": fit-display, numbered-display
#import "main-defs.typ": reference-rules, russian-typography

#let matrix-cell-text(cell) = {
  let fields = cell.fields()
  if "text" in fields { fields.text } else if "children" in fields {
    let parts = fields.children.map(matrix-cell-text)
    if parts.all(part => part != none) { parts.join() } else { none }
  } else { none }
}

#let heading-anchor(it) = {
  restart-counters(it.level)
  [#metadata((kind: "numbered", family: "heading", level: it.level))<numbered>]
}

#let running-chapter = state("running-chapter", none)
#let running-section = state("running-section", none)

#let heading-number(it) = counter(heading).at(it.location())

#let section-title(it) = [§ #heading-number(it).at(0).#heading-number(it).at(1).
  #it.body]

#let is-reference-chapter(it) = (
  it.has("label") and it.label == <ch:reference>
)

#let opening-page() = {
  query(heading.where(level: 1))
    .map(it => it.location().page())
    .contains(here().page())
}

#let running-header = {
  set par(justify: false, first-line-indent: 0pt)
  context {
    let number = counter(page).get().first()
    if opening-page() { return }
    let folio = counter(page).display()
    let head = text.with(size: 10pt)
    if calc.even(number) {
      let chapter = running-chapter.get()
      if chapter == none { return }
      grid(
        columns: (2em, 1fr, 2em),
        column-gutter: 0.65em,
        align: (left, center, right),
        head(folio), head(chapter), [],
      )
    } else {
      let beginning = query(heading.where(level: 2)).filter(it => (
        it.numbering != none and it.location().page() == here().page()
      ))
      let section = if beginning.len() > 0 {
        section-title(beginning.first())
      } else { running-section.get() }
      if section == none { section = running-chapter.get() }
      if section == none { return }
      grid(
        columns: (2em, 1fr, 2em),
        column-gutter: 0.65em,
        align: (left, center, right),
        [], head(section), head(folio),
      )
    }
  }
}

#let running-footer = context {
  if opening-page() {
    align(center, text(size: 10pt, counter(page).display()))
  }
}

#let book-style(body) = {
  show: russian-typography
  set page(
    width: 5.5in,
    height: 8.5in,
    margin: (x: 16mm, top: 20mm, bottom: 18mm),
    header: counter(footnote).update(0) + running-header,
    footer: running-footer,
  )
  set text(
    font: "Libertinus Serif",
    size: 11pt,
    lang: "ru",
    region: "ru",
    fill: rgb("202020"),
  )
  show link: set text(fill: rgb("202020"))
  show regex("^-\p{L}"): it => sym.wj + it
  show "–": it => sym.wj + it + sym.wj
  set par(
    justify: true,
    leading: 0.52em,
    first-line-indent: 1.25em,
    spacing: 0.7em,
  )
  set enum(numbering: "(1)")
  set heading(numbering: (..n) => {
    let n = n.pos()
    if n.len() == 1 { "Глава " + str(n.at(0)) + "." } else if n.len() == 2 {
      "§ " + str(n.at(0)) + "." + str(n.at(1)) + "."
    } else { str(n.last()) + "°." }
  })

  show heading.where(level: 1): it => {
    pagebreak(weak: true)
    let numbered = it.numbering != none and not is-reference-chapter(it)
    let title = if numbered {
      [Глава #heading-number(it).first(). #it.body]
    } else { it.body }
    running-chapter.update(title)
    running-section.update(none)
    set par(first-line-indent: 0pt, justify: false)
    if it.numbering != none { heading-anchor(it) }
    block(width: 100%, above: 9mm, below: 8mm, align(center, {
      if numbered {
        text(size: 17pt, weight: "regular")[Глава #heading-number(it).first()]
        linebreak()
      }
      text(size: 17pt, weight: "regular", it.body)
    }))
  }

  show heading.where(level: 2): it => {
    set par(first-line-indent: 0pt, justify: false)
    if it.numbering == none {
      block(width: 100%, above: 7mm, below: 4mm, sticky: true, strong(it.body))
    } else {
      running-section.update(section-title(it))
      heading-anchor(it)
      block(width: 100%, above: 6mm, below: 4mm, sticky: true, align(
        center,
        text(size: 15pt, weight: "regular", section-title(it)),
      ))
    }
  }

  show heading.where(level: 3): it => {
    set par(first-line-indent: 0pt, justify: false)
    if it.numbering == none and it.supplement == [Table] {
      block(width: 100%, above: 7mm, below: 3mm, sticky: true, strong(
        it.body,
      ))
    } else if it.numbering == none {
      block(width: 100%, above: 7mm, below: 4mm, sticky: true, align(
        center,
        strong(it.body),
      ))
    } else {
      heading-anchor(it)
      block(width: 100%, above: 6mm, below: 3mm, sticky: true, strong[
        #heading-number(it).last()°. #it.body
      ])
    }
  }

  show outline: set par(first-line-indent: 0pt)
  show outline.entry: set block(breakable: false)
  show outline.entry.where(level: 1): set block(above: 1.1em)
  show outline.entry: it => link(
    it.element.location(),
    it.indented(
      if it.element.numbering == none { none } else {
        let n = heading-number(it.element)
        if it.level == 1 {
          if is-reference-chapter(it.element) { none } else [
            Глава #n.first().
          ]
        } else if it.level == 2 [§ #n.at(0).#n.at(1).] else [#n.last()°.]
      },
      it.inner(),
    ),
  )

  set math.equation(numbering: none, supplement: none)
  show math.equation: set text(font: "STIX Two Math")
  show math.equation: it => {
    show ":": math.class("punctuation", ":")
    show "≥": sym.gt.eq.slant
    show "≤": sym.lt.eq.slant
    show regex("[\u{0391}-\u{03A9}]"): math.italic
    it
  }
  show math.mat: it => {
    let cells = it.rows.flatten().map(matrix-cell-text)
    let signed-atoms = (
      cells.all(cell => (
        cell != none
          and cell.match(
            regex("^−?([0-9]+|[A-Za-zΑ-Ωα-ω])$"),
          )
            != none
      ))
        and cells.any(cell => cell != none and cell.starts-with("−"))
    )
    if signed-atoms and it.align != right {
      let fields = it.fields()
      let rows = fields.remove("rows")
      fields.insert("align", right)
      math.display(math.mat(..rows, ..fields))
    } else { math.display(it) }
  }
  set math.cases(gap: 0.6em)

  set table(stroke: 0.5pt, inset: (x: 0.45em, y: 0.5em), align: horizon)
  set table.cell(breakable: false)
  show table: set text(size: 10pt)
  show table: set par(justify: false, first-line-indent: 0pt)
  let list-item(body) = {
    let first = if body.func() == [].func() {
      body.children.find(it => it != [ ])
    } else { body }
    (
      first != none
        and first.func() == text
        and first.text.match(regex("^[a-z]\)$")) != none
    )
  }
  show math.equation.where(block: true): it => {
    if it.body.func() == grid and not it.has("label") {
      return {
        set block(breakable: true)
        align(center, it.body)
      }
    }
    set align(start) if list-item(it.body)
    let numbered = (
      it.numbering == none
        and it.has("label")
        and str(it.label).starts-with("eq:")
    )
    if numbered { numbered-display(it) } else { fit-display(it) }
  }

  show: reference-rules
  set footnote(numbering: "1)")
  show footnote: it => sym.wj + it
  show footnote.entry: it => block(breakable: false, it)
  set footnote.entry(separator: line(length: 25%, stroke: 0.5pt))
  body
}
