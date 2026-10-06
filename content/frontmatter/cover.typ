#import "../main-defs.typ": source

#let cover() = {
  set page(
    width: 5.5in,
    height: 8.5in,
    margin: 0pt,
    numbering: none,
    header: none,
    footer: none,
    fill: rgb("111111"),
  )
  set text(font: "PT Sans", weight: "bold", fill: rgb("c9a15c"))
  place(top + left, dx: 18pt, dy: 290pt, text(size: 26pt)[НЕКОММУТАТИВНЫЕ
    КОЛЬЦА])
  place(top + left, dx: 18pt, dy: 322pt, line(
    length: 360pt,
    stroke: .65pt + rgb("d4cba7"),
  ))
  place(top + right, dx: -18pt, dy: 336pt, text(size: 21pt)[И. ХЕРСТЕЙН])
  source(1, printed: "обложка")
  box(width: 0pt, height: 0pt)
}
