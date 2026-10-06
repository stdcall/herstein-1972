// Readable list of the confirmed deviations of this edition from the
// printed book (corrections.json), built as a separate PDF. An entry prints
// its id, printed page, place, the printed reading, the correction and the
// reason; `verified_by` (how the correction was checked) stays in the
// journal.
//
// `original`, `corrected` and `reason` are Typst markup: most entries quote
// formulas, so they are evaluated with the book's own definitions (GL, Ad,
// the reference helpers are not needed here) to read as in the book.
#import "main-defs.typ" as book-defs

// The entries quote the printed numbering. The corresponding objects are
// in the book, so their numbers are literal quotations in this document.
#show: book-defs.reference-rules
#show: book-defs.russian-typography
#let book-scope = dictionary(book-defs)
#let entries = json("../corrections.json").entries
#let markup(field) = eval(field, mode: "markup", scope: book-scope)

#set document(
  title: "Херстейн: Некоммутативные кольца. Исправления",
  author: ("И. Херстейн",),
  date: none,
)
#set page(
  width: 176mm,
  height: 250mm,
  margin: (x: 20mm, top: 21mm, bottom: 21mm),
  footer: context align(center, text(size: 10pt, counter(page).display())),
)
#set text(font: "Libertinus Serif", size: 11pt, lang: "ru", region: "ru")
#set par(justify: true, leading: 0.65em, spacing: 0.8em)
#show math.equation: set text(font: "STIX Two Math")
#show math.equation: it => {
  show ":": math.class("punctuation", ":")
  show "≥": sym.gt.eq.slant
  show "≤": sym.lt.eq.slant
  show regex("[\u{0391}-\u{03A9}]"): math.italic
  it
}

#align(center, text(size: 16pt)[Исправления])

И.~Херстейн, _Некоммутативные кольца_, Мир, Москва, 1972. В этом издании
исправлены перечисленные ниже опечатки и ошибки. Номера страниц относятся к
печатной книге.

// The entries go by the page of the book and are grouped under the part of
// the book they belong to ("Chapter 4, § 2"), a heading and a bookmark each;
// an entry names its own place only where it is narrower than the part.
#show heading: set text(size: 12pt)
#show heading: set block(above: 1.6em, below: 0.8em)

#if entries.len() == 0 [
  Исправления не зарегистрированы.
] else {
  let section = none
  for entry in entries {
    if entry.section != section {
      section = entry.section
      heading(level: 1, section)
    }
    block(breakable: false, above: 1em)[
      #metadata((correction: entry.id))
      *#entry.id* · с. #entry.printed_page#if (
        entry.place != entry.section
      ) [, #entry.place]

      В книге: #markup(entry.original)

      Исправлено: #markup(entry.corrected)

      #text(size: 10pt, markup(entry.reason))
    ]
  }
}
