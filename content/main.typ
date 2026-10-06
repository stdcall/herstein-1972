// The book in reading order.
#set document(
  title: "Некоммутативные кольца",
  author: ("И. Херстейн",),
  date: none,
)
#import "frontmatter/cover.typ": cover
#cover()
#pagebreak()
#import "frontmatter/frontmatter-style.typ": front-blank, frontmatter-style
#frontmatter-style[
  #include "frontmatter/02-english-title.typ"
  #include "frontmatter/03-russian-title.typ"
  #include "frontmatter/04-annotation.typ"
  #include "00-editor-preface.typ"
  #front-blank(6)
  #include "00-preface.typ"
]
#pagebreak()
#import "book-style.typ": book-style
#show: book-style
#set page(numbering: "1")
#include "10-jacobson-radical.typ"
#include "11-modules.typ"
#include "12-radical.typ"
#include "13-artinian-rings.typ"
#include "14-semisimple-artinian.typ"
#include "20-dense-rings.typ"
#include "21-density.typ"
#include "22-semisimple-rings.typ"
#include "23-density-applications.typ"
#include "30-commutativity.typ"
#include "31-wedderburn.typ"
#include "32-special-rings.typ"
#include "40-finite-dimensional-division.typ"
#include "41-brauer.typ"
#include "42-maximal-subfields.typ"
#include "43-classical-theorems.typ"
#include "44-crossed-products.typ"
#include "50-representations.typ"
#include "51-representations-elements.typ"
#include "52-hurwitz.typ"
#include "53-representations-applications.typ"
#include "60-polynomial-identities.typ"
#include "61-pi-radical.typ"
#include "62-standard-identities.typ"
#include "63-kaplansky.typ"
#include "64-kurosh-problem.typ"
#include "70-quotient-rings.typ"
#include "71-ore.typ"
#include "72-goldie.typ"
#include "73-ultraproducts.typ"
#include "80-golod-shafarevitch.typ"
#include "89-bibliography.typ"
#include "94-editorial-bibliography.typ"
#include "91-name-index.typ"
#include "90-index.typ"
#import "main-defs.typ": source
#source(190)
#heading(level: 1, numbering: none, outlined: false)[Оглавление]
<part:contents>
#outline(title: none, depth: 2)
