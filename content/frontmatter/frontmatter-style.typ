#import "../bibliography-data.typ": bibliography-data
#import "../main-defs.typ": reference-rules, russian-typography, source

#let front-page-start(n) = {
  pagebreak(weak: true)
  counter(page).update(n)
}

#let front-blank(n) = {
  front-page-start(n)
  box(width: 0pt, height: 0pt)
}

#let frontmatter-style(body) = {
  show: russian-typography
  show: reference-rules
  set page(
    width: 5.5in,
    height: 8.5in,
    margin: (x: 16mm, top: 20mm, bottom: 18mm),
    numbering: "1",
    header: context {
      let n = counter(page).get().first()
      if n == 8 {
        grid(
          columns: (2em, 1fr, 2em),
          [#n], align(center)[_Предисловие_], [],
        )
      }
    },
    footer: none,
  )
  set text(font: "Libertinus Serif", size: 11pt, lang: "ru")
  show math.equation: set text(font: "STIX Two Math")
  set par(
    justify: true,
    leading: .52em,
    spacing: .7em,
    first-line-indent: 1.25em,
  )
  set heading(numbering: none)
  set footnote(numbering: "1)")
  show footnote: it => sym.wj + it
  show footnote.entry: it => block(breakable: false, it)
  set footnote.entry(separator: line(length: 25%, stroke: 0.5pt))
  show heading: it => block(width: 100%, below: 1em, align(center, text(
    size: 13pt,
    it.body,
  )))
  body
}

#let front-centered(body, size: 11pt) = {
  set par(first-line-indent: 0pt, justify: false)
  align(center, text(size: size, body))
}
#let front-space(amount) = v(amount)
#let front-signature(body) = align(right, emph(body))
#let front-dedication(body) = {
  align(right, emph(body))
  v(10mm)
}
#let front-work(key) = emph(bibliography-data.at(key).title)
#let front-author(key) = bibliography-data.at(key).author
#let front-imprint(key) = {
  let e = bibliography-data.at(key)
  [#front-work(key), #e.publisher, #e.location, #e.year]
}
#let front-publication(key) = {
  let e = bibliography-data.at(key)
  [#e.publisher, #e.location, #e.year]
}
